"""Automated benchmarking framework for CallLens Stress Lab.

Orchestrates:
- Experiment A: 30 FLEURS clips x 4 conditions x 2 models = 240 STT evaluations
- Experiment D: 20 noise/silence clips x 2 models = 40 STT evaluations
- Experiment F: 10 BFSI utterances x 4 conditions x 2 models = 80 STT evaluations
Total: 360 logical STT evaluations.

Features:
- SQLAlchemy SQLite storage
- Resumable execution (skips completed evaluations)
- Bootstrap 95% confidence intervals (seed 0, 1000 resamples)
- Dry-run mode and scale control (--scale 0.1 / 1.0)
- Matplotlib chart generation (WER by condition with CIs, WER vs P95 latency)
- tests/results.md generation
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import soundfile as sf
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from calllens import degrade, extract, gnani_client, metrics
from calllens.gnani_client import accounting

Base = declarative_base()


class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    experiment = Column(String(10), nullable=False)  # A, D, F
    clip_id = Column(String(64), nullable=False)
    condition = Column(String(32), nullable=False)  # clean, tel, tel_snr10, tel_snr0
    model = Column(String(32), nullable=False)  # prisma-v2.5, prisma-v3.0
    format = Column(String(32), nullable=False)  # verbatim

    reference_text = Column(Text, nullable=True)
    hypothesis_text = Column(Text, nullable=True)
    normalized_ref = Column(Text, nullable=True)
    normalized_hyp = Column(Text, nullable=True)

    wer = Column(Float, nullable=True)
    cer = Column(Float, nullable=True)
    latency_sec = Column(Float, nullable=False)
    duration_sec = Column(Float, nullable=False)
    rtf = Column(Float, nullable=False)

    gt_amount = Column(Integer, nullable=True)
    extracted_amount = Column(Integer, nullable=True)
    amount_correct = Column(Boolean, nullable=True)

    gt_due_day = Column(Integer, nullable=True)
    extracted_due_day = Column(Integer, nullable=True)
    due_day_correct = Column(Boolean, nullable=True)

    is_hallucinated = Column(Boolean, nullable=True)
    from_cache = Column(Boolean, default=False)
    mock = Column(Boolean, default=False)
    provenance = Column(String(16), nullable=False, default="live")  # 'live' or 'mock'
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def get_db_session(db_url: str):
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def load_manifest(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_benchmark(
    scale: float = 1.0,
    live: bool = False,
    dry_run: bool = False,
    db_url: str | None = None,
    output_report_path: Path | None = None,
    chart_dir: Path | None = None,
) -> dict[str, Any]:
    data_dir = Path(os.getenv("DATA_DIR", "../calllens-data"))
    if db_url is None:
        db_path = os.getenv("DATABASE_URL", f"sqlite:///{data_dir}/benchmark.db")
        db_url = db_path

    if chart_dir is None:
        chart_dir = Path("docs")
    chart_dir.mkdir(parents=True, exist_ok=True)

    if output_report_path is None:
        output_report_path = Path("tests/results.md")
    output_report_path.parent.mkdir(parents=True, exist_ok=True)

    fleurs_manifest = load_manifest(data_dir / "fleurs" / "manifest.json")
    noise_manifest = load_manifest(data_dir / "noise_silence" / "manifest.json")
    bfsi_manifest = load_manifest(data_dir / "bfsi" / "manifest.json")
    bfsi_gt = {item["clip_id"]: item for item in load_manifest(data_dir / "bfsi" / "ground_truth.json")}

    # Apply scaling
    if scale < 1.0:
        n_a = max(1, int(round(len(fleurs_manifest) * scale)))
        n_d = max(2, int(round(len(noise_manifest) * scale)))
        n_f = max(1, int(round(len(bfsi_manifest) * scale)))
        fleurs_manifest = fleurs_manifest[:n_a]
        noise_manifest = noise_manifest[:n_d]
        bfsi_manifest = bfsi_manifest[:n_f]

    models = [
        {"name": "prisma-v2.5", "param": None},
        {"name": "prisma-v3.0", "param": "prisma-v3.0"},
    ]
    conditions = ["clean", "tel", "tel_snr10", "tel_snr0"]

    # Calculate planned logical calls
    plan_a = len(fleurs_manifest) * len(conditions) * len(models)
    plan_d = len(noise_manifest) * len(models)
    plan_f = len(bfsi_manifest) * len(conditions) * len(models)
    total_planned = plan_a + plan_d + plan_f

    print("=" * 60)
    print("CALLLENS BENCHMARK EXECUTION")
    print(f"Mode: {'DRY RUN' if dry_run else ('LIVE API' if live else 'MOCK / REPRODUCIBLE')}")
    print(f"Scale: {scale:.1f} ({scale*100:.0f}%)")
    print(f"Planned Logical Evaluations:")
    print(f"  Experiment A (FLEURS):   {plan_a} ({len(fleurs_manifest)} clips x 4 cond x 2 models)")
    print(f"  Experiment D (Noise):    {plan_d} ({len(noise_manifest)} clips x 2 models)")
    print(f"  Experiment F (BFSI):     {plan_f} ({len(bfsi_manifest)} clips x 4 cond x 2 models)")
    print(f"  TOTAL STT EVALUATIONS:   {total_planned}")
    print(f"Database: {db_url}")
    print("=" * 60)

    if dry_run:
        print("\nDry run completed successfully. No API calls or database writes executed.")
        return {"planned_calls": total_planned, "dry_run": True}

    session = get_db_session(db_url)
    processed_audio_dir = data_dir / "processed_audio"
    processed_audio_dir.mkdir(parents=True, exist_ok=True)

    completed_count = 0

    # 1. Execute Experiment A (FLEURS Hindi Robustness)
    print("\n--- Running Experiment A: Hindi ASR Telephony Robustness ---")
    for clip in fleurs_manifest:
        orig_path = Path(clip["file_path"])
        clip_id = clip["clip_id"]
        raw_ref = clip["raw_transcription"]

        for cond in conditions:
            # Generate degraded audio if not exists
            deg_path = processed_audio_dir / f"{clip_id}_{cond}.wav"
            if not deg_path.exists() or deg_path.stat().st_mtime < orig_path.stat().st_mtime:
                degrade.process_audio_file(orig_path, deg_path, condition=cond, clip_id=clip_id)

            info = sf.info(str(deg_path))
            dur = info.duration

            for m in models:
                # Check DB for existing record (resumable)
                prov_filter = "live" if live else "mock"
                existing = session.query(BenchmarkResult).filter_by(
                    experiment="A",
                    clip_id=clip_id,
                    condition=cond,
                    model=m["name"],
                    provenance=prov_filter,
                ).first()

                if existing:
                    completed_count += 1
                    continue

                # Prepare payload
                # In mock mode, supply a realistic degraded transcript
                mock_text = raw_ref
                if cond == "tel_snr10":
                    words = raw_ref.split()
                    if len(words) > 3:
                        # Introduce a minor substitution for v2.5, fewer for v3.0
                        if m["name"] == "prisma-v2.5":
                            words[-2] = "और"
                        mock_text = " ".join(words)
                elif cond == "tel_snr0":
                    words = raw_ref.split()
                    if len(words) > 4:
                        if m["name"] == "prisma-v2.5":
                            words[1] = "भी"
                            words[-2] = "है"
                        else:
                            words[-2] = "है"
                        mock_text = " ".join(words)

                payload = {
                    "audio": deg_path,
                    "model": m["param"],
                    "language_code": "hi-IN",
                    "format": "verbatim",
                    "mock_transcript": mock_text,
                }

                res = gnani_client.call("stt", payload, live=live)
                hyp = res.get("transcript", "")
                lat = res.get("end_to_end_latency", 0.5)

                wer_val = metrics.compute_wer(raw_ref, hyp)
                cer_val = metrics.compute_cer(raw_ref, hyp)

                prov_val = "live" if (live and not res.get("mock", False)) else "mock"
                rec = BenchmarkResult(
                    experiment="A",
                    clip_id=clip_id,
                    condition=cond,
                    model=m["name"],
                    format="verbatim",
                    reference_text=raw_ref,
                    hypothesis_text=hyp,
                    normalized_ref=metrics.normalize_text(raw_ref),
                    normalized_hyp=metrics.normalize_text(hyp),
                    wer=wer_val,
                    cer=cer_val,
                    latency_sec=lat,
                    duration_sec=dur,
                    rtf=round(lat / max(dur, 0.01), 4),
                    from_cache=res.get("from_cache", False),
                    mock=res.get("mock", False),
                    provenance=prov_val,
                )
                session.add(rec)
                session.commit()
                completed_count += 1

    # 2. Execute Experiment D (Noise & Silence Hallucination)
    print("\n--- Running Experiment D: Noise & Silence Hallucination ---")
    for clip in noise_manifest:
        orig_path = Path(clip["file_path"])
        clip_id = clip["clip_id"]
        info = sf.info(str(orig_path))
        dur = info.duration

        for m in models:
            prov_filter = "live" if live else "mock"
            existing = session.query(BenchmarkResult).filter_by(
                experiment="D",
                clip_id=clip_id,
                condition="clean",
                model=m["name"],
                provenance=prov_filter,
            ).first()

            if existing:
                completed_count += 1
                continue

            payload = {
                "audio": orig_path,
                "model": m["param"],
                "language_code": "hi-IN",
                "format": "verbatim",
                "mock_transcript": "",  # Standard noise/silence produces empty transcript
            }

            res = gnani_client.call("stt", payload, live=live)
            hyp = res.get("transcript", "")
            lat = res.get("end_to_end_latency", 0.4)
            norm_hyp = metrics.normalize_text(hyp)
            hallucinated = (norm_hyp != "")

            prov_val = "live" if (live and not res.get("mock", False)) else "mock"
            rec = BenchmarkResult(
                experiment="D",
                clip_id=clip_id,
                condition="clean",
                model=m["name"],
                format="verbatim",
                reference_text="",
                hypothesis_text=hyp,
                normalized_ref="",
                normalized_hyp=norm_hyp,
                is_hallucinated=hallucinated,
                latency_sec=lat,
                duration_sec=dur,
                rtf=round(lat / max(dur, 0.01), 4),
                from_cache=res.get("from_cache", False),
                mock=res.get("mock", False),
                provenance=prov_val,
            )
            session.add(rec)
            session.commit()
            completed_count += 1

    # 3. Execute Experiment F (BFSI Entity Extraction)
    print("\n--- Running Experiment F: BFSI Entity Extraction ---")
    for clip in bfsi_manifest:
        orig_path = Path(clip["file_path"])
        clip_id = clip["clip_id"]
        gt = bfsi_gt.get(clip_id, {})
        gt_amt = gt.get("amount")
        gt_day = gt.get("due_day")
        raw_ref = clip.get("text", "")

        for cond in conditions:
            deg_path = processed_audio_dir / f"{clip_id}_{cond}.wav"
            if not deg_path.exists() or deg_path.stat().st_mtime < orig_path.stat().st_mtime:
                degrade.process_audio_file(orig_path, deg_path, condition=cond, clip_id=clip_id)

            info = sf.info(str(deg_path))
            dur = info.duration

            for m in models:
                prov_filter = "live" if live else "mock"
                existing = session.query(BenchmarkResult).filter_by(
                    experiment="F",
                    clip_id=clip_id,
                    condition=cond,
                    model=m["name"],
                    provenance=prov_filter,
                ).first()

                if existing:
                    completed_count += 1
                    continue

                mock_text = raw_ref
                # On tel_snr0, occasionally obscure amount or day
                if cond == "tel_snr0" and m["name"] == "prisma-v2.5":
                    mock_text = raw_ref.replace("हजार", "सौ")

                payload = {
                    "audio": deg_path,
                    "model": m["param"],
                    "language_code": "hi-IN",
                    "format": "verbatim",
                    "mock_transcript": mock_text,
                }

                res = gnani_client.call("stt", payload, live=live)
                hyp = res.get("transcript", "")
                lat = res.get("end_to_end_latency", 0.5)

                pred_entities = extract.extract_entities(hyp)
                amt_corr = (pred_entities.get("amount") == gt_amt)
                day_corr = (pred_entities.get("due_day") == gt_day)

                wer_val = metrics.compute_wer(raw_ref, hyp)
                cer_val = metrics.compute_cer(raw_ref, hyp)

                prov_val = "live" if (live and not res.get("mock", False)) else "mock"
                rec = BenchmarkResult(
                    experiment="F",
                    clip_id=clip_id,
                    condition=cond,
                    model=m["name"],
                    format="verbatim",
                    reference_text=raw_ref,
                    hypothesis_text=hyp,
                    normalized_ref=metrics.normalize_text(raw_ref),
                    normalized_hyp=metrics.normalize_text(hyp),
                    wer=wer_val,
                    cer=cer_val,
                    gt_amount=gt_amt,
                    extracted_amount=pred_entities.get("amount"),
                    amount_correct=amt_corr,
                    gt_due_day=gt_day,
                    extracted_due_day=pred_entities.get("due_day"),
                    due_day_correct=day_corr,
                    latency_sec=lat,
                    duration_sec=dur,
                    rtf=round(lat / max(dur, 0.01), 4),
                    from_cache=res.get("from_cache", False),
                    mock=res.get("mock", False),
                    provenance=prov_val,
                )
                session.add(rec)
                session.commit()
                completed_count += 1

    print(f"\nBenchmark completed. Total records processed/verified: {completed_count}")

    # Generate Statistical Report and Charts
    target_prov = "live" if live else "mock"
    generate_summary_report(session, output_report_path, provenance=target_prov)
    generate_charts(session, chart_dir, provenance=target_prov)

    return {
        "total_evaluations": completed_count,
        "database_url": db_url,
        "report_path": str(output_report_path),
        "chart_dir": str(chart_dir),
    }


def generate_summary_report(session, report_path: Path, provenance: str = "live") -> None:
    """Generates markdown report strictly filtered by provenance ('live' or 'mock').
    Ensures that mock and live data are never mixed in any aggregation.
    """
    total_recs = session.query(BenchmarkResult).filter_by(provenance=provenance).count()
    if total_recs == 0:
        lines = [
            f"# CallLens Stress Lab — Benchmark Results ({provenance.upper()} DATA)",
            "",
            f"> Generated on: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"> Data Provenance Filter: {provenance.upper()} (Strict Isolation)",
            "",
            f"**No {provenance} results yet.**",
            "",
            f"The database contains 0 records matching provenance '{provenance}'. No mock data is shown or mixed with live results.",
        ]
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"Summary report generated: {report_path} (0 {provenance} records)")
        return

    lines = [
        f"# CallLens Stress Lab — Benchmark Results ({provenance.upper()} DATA)",
        "",
        f"> Generated on: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"> Data Provenance: {provenance.upper()} (Strict Isolation - No Mock Data Mixed)",
        "",
        "## Summary Overview",
        "",
        f"This report documents experimental evaluations comparing **Gnani Prisma v2.5** and **Gnani Prisma v3.0** under clean and simulated telephony degradation conditions ({provenance.upper()} provenance).",
        "",
        "**Important Methodology Notice:** Telephony channel degradation was applied deterministically to read speech (FLEURS) and synthetic TTS speech (Timbre v2.5). This evaluates acoustic robustness under simulated channel degradation and noise; it does not replace testing on real human customer call center recordings.",
        "",
        "---",
        "",
        "## Experiment A: Hindi ASR Telephony Robustness (FLEURS)",
        "",
        "Evaluates 30 FLEURS Hindi India clips (CC BY 4.0, <= 28 seconds) across 4 acoustic conditions with 95% clip-level bootstrap confidence intervals (1,000 resamples, seed 0).",
        "",
        "| Model | Condition | N | Mean WER | 95% CI (WER) | Mean CER | P50 Latency (s) | P95 Latency (s) | Mean RTF |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]

    for model_name in ["prisma-v2.5", "prisma-v3.0"]:
        for cond in ["clean", "tel", "tel_snr10", "tel_snr0"]:
            recs = session.query(BenchmarkResult).filter_by(
                experiment="A",
                model=model_name,
                condition=cond,
                provenance=provenance,
            ).all()

            if not recs:
                continue

            wers = [r.wer for r in recs if r.wer is not None]
            cers = [r.cer for r in recs if r.cer is not None]
            lats = [r.latency_sec for r in recs]
            durs = [r.duration_sec for r in recs]

            mean_wer, ci_l, ci_u = metrics.compute_bootstrap_ci(wers, n_resamples=1000, seed=0)
            mean_cer = round(float(np.mean(cers)), 4) if cers else 0.0
            lat_stats = metrics.compute_latency_stats(lats, durs)

            lines.append(
                f"| {model_name} | {cond} | {len(recs)} | {mean_wer:.4f} | [{ci_l:.4f}, {ci_u:.4f}] | {mean_cer:.4f} | {lat_stats['p50']:.3f} | {lat_stats['p95']:.3f} | {lat_stats['rtf']:.3f} |"
            )

    lines.extend([
        "",
        "---",
        "",
        "## Experiment D: Noise & Silence Hallucination",
        "",
        "Evaluates 20 five-second clips (10 white noise, 10 silence) to measure false-text hallucination rate.",
        "",
        "| Model | Input Type | N | Hallucinated Count | False-Text Rate | Mean Latency (s) |",
        "| :--- | :--- | :---: | :---: | :---: | :---: |",
    ])

    for model_name in ["prisma-v2.5", "prisma-v3.0"]:
        recs = session.query(BenchmarkResult).filter_by(
            experiment="D",
            model=model_name,
            provenance=provenance,
        ).all()

        if recs:
            hall_count = sum(1 for r in recs if r.is_hallucinated)
            rate = round(hall_count / len(recs), 4)
            mean_lat = round(float(np.mean([r.latency_sec for r in recs])), 3)
            lines.append(
                f"| {model_name} | Noise & Silence | {len(recs)} | {hall_count} | {rate:.4f} | {mean_lat:.3f} |"
            )

    lines.extend([
        "",
        "---",
        "",
        "## Experiment F: BFSI Entity Extraction Accuracy",
        "",
        "Evaluates exact-match extraction accuracy for payment amounts and due days across 10 synthetic Hinglish banking utterances under 4 degradation conditions.",
        "",
        "| Model | Condition | N | Amount Accuracy | Due-Day Accuracy | Both Correct | Mean WER |",
        "| :--- | :--- | :---: | :---: | :---: | :---: | :---: |",
    ])

    for model_name in ["prisma-v2.5", "prisma-v3.0"]:
        for cond in ["clean", "tel", "tel_snr10", "tel_snr0"]:
            recs = session.query(BenchmarkResult).filter_by(
                experiment="F",
                model=model_name,
                condition=cond,
                provenance=provenance,
            ).all()

            if not recs:
                continue

            n = len(recs)
            amt_acc = sum(1 for r in recs if r.amount_correct) / n
            day_acc = sum(1 for r in recs if r.due_day_correct) / n
            both_acc = sum(1 for r in recs if (r.amount_correct and r.due_day_correct)) / n
            wers = [r.wer for r in recs if r.wer is not None]
            mean_wer = float(np.mean(wers)) if wers else 0.0

            lines.append(
                f"| {model_name} | {cond} | {n} | {amt_acc:.4f} | {day_acc:.4f} | {both_acc:.4f} | {mean_wer:.4f} |"
            )

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Summary report generated: {report_path}")


def generate_charts(session, chart_dir: Path, provenance: str = "live") -> None:
    """Generates publication-quality charts strictly from records matching provenance.
    Ensures no mock data is mixed with live data.
    """
    total_recs = session.query(BenchmarkResult).filter_by(provenance=provenance).count()
    if total_recs == 0:
        print(f"No {provenance} records found in database. Skipping chart generation to prevent misleading visualizations.")
        return

    conditions = ["clean", "tel", "tel_snr10", "tel_snr0"]
    models = ["prisma-v2.5", "prisma-v3.0"]

    # Chart 1: WER across conditions with 95% CIs
    data: dict[str, list[float]] = {m: [] for m in models}
    err_low: dict[str, list[float]] = {m: [] for m in models}
    err_high: dict[str, list[float]] = {m: [] for m in models}
    p95_lats: dict[str, list[float]] = {m: [] for m in models}

    for m in models:
        for c in conditions:
            recs = session.query(BenchmarkResult).filter_by(
                experiment="A",
                model=m,
                condition=c,
                provenance=provenance,
            ).all()

            if recs:
                wers = [r.wer for r in recs if r.wer is not None]
                mean_wer, ci_l, ci_u = metrics.compute_bootstrap_ci(wers, n_resamples=1000, seed=0)
                data[m].append(mean_wer)
                err_low[m].append(max(0.0, mean_wer - ci_l))
                err_high[m].append(max(0.0, ci_u - mean_wer))

                lats = [r.latency_sec for r in recs]
                lat_stats = metrics.compute_latency_stats(lats)
                p95_lats[m].append(lat_stats["p95"])
            else:
                data[m].append(0.0)
                err_low[m].append(0.0)
                err_high[m].append(0.0)
                p95_lats[m].append(0.0)

    # 1. Plot WER by Condition with Confidence Intervals
    fig, ax = plt.subplots(figsize=(9, 5), dpi=150)
    x = np.arange(len(conditions))
    width = 0.35

    ax.bar(
        x - width / 2,
        data["prisma-v2.5"],
        width,
        yerr=[err_low["prisma-v2.5"], err_high["prisma-v2.5"]],
        capsize=5,
        label="Prisma v2.5",
        color="#2b5c8f",
        edgecolor="black",
        alpha=0.9,
    )
    ax.bar(
        x + width / 2,
        data["prisma-v3.0"],
        width,
        yerr=[err_low["prisma-v3.0"], err_high["prisma-v3.0"]],
        capsize=5,
        label="Prisma v3.0",
        color="#00a86b",
        edgecolor="black",
        alpha=0.9,
    )

    ax.set_ylabel("Word Error Rate (WER)")
    ax.set_title(f"Hindi Speech Recognition: WER across Degradation Conditions ({provenance.upper()} Data, 95% CI)")
    ax.set_xticks(x)
    ax.set_xticklabels(["Clean\n(16kHz)", "Telephony\n(300-3400Hz)", "Tel + 10dB SNR\n(White Noise)", "Tel + 0dB SNR\n(Heavy Noise)"])
    ax.legend(frameon=True)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.set_ylim(0, max(0.4, max(data["prisma-v2.5"] + data["prisma-v3.0"]) * 1.3))

    chart1_path = chart_dir / "wer_by_condition.png"
    plt.tight_layout()
    plt.savefig(chart1_path)
    plt.close()
    print(f"Chart saved: {chart1_path}")

    # 2. Plot WER vs P95 Latency
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    colors = {"prisma-v2.5": "#2b5c8f", "prisma-v3.0": "#00a86b"}
    markers = {"prisma-v2.5": "o", "prisma-v3.0": "s"}

    for m in models:
        ax.scatter(
            p95_lats[m],
            data[m],
            color=colors[m],
            marker=markers[m],
            s=120,
            label=m,
            edgecolors="black",
            alpha=0.9,
        )
        for i, txt in enumerate(conditions):
            ax.annotate(
                f"{txt}",
                (p95_lats[m][i], data[m][i]),
                textcoords="offset points",
                xytext=(5, 5),
                fontsize=8,
            )

    ax.set_xlabel("P95 Latency (seconds)")
    ax.set_ylabel("Word Error Rate (WER)")
    ax.set_title(f"CallLens: WER vs P95 Latency Trade-off ({provenance.upper()} Data)")
    ax.legend(frameon=True)
    ax.grid(True, linestyle="--", alpha=0.3)

    chart2_path = chart_dir / "wer_vs_latency.png"
    plt.tight_layout()
    plt.savefig(chart2_path)
    plt.close()
    print(f"Chart saved: {chart2_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CallLens Benchmark")
    parser.add_argument("--scale", type=float, default=1.0, help="Fraction of dataset to evaluate (e.g. 0.1 or 1.0)")
    parser.add_argument("--live", action="store_true", help="Execute live network calls via Gnani API")
    parser.add_argument("--dry-run", action="store_true", help="Print call plan without executing")
    parser.add_argument("--db-url", type=str, default=None, help="Database connection URL")
    args = parser.parse_args()

    run_benchmark(
        scale=args.scale,
        live=args.live,
        dry_run=args.dry_run,
        db_url=args.db_url,
    )
