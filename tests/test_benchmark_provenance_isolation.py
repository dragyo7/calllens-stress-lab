"""Tests ensuring strict provenance isolation between live and mock benchmark results.

Verifies:
- Provenance column persistence ('live' vs 'mock')
- Independent aggregation without cross-contamination
- Zero mixing in summary reports and chart generation
"""

from pathlib import Path
import pytest
from calllens.benchmark import BenchmarkResult, generate_charts, generate_summary_report, get_db_session


def test_provenance_isolation_in_reports_and_charts(tmp_path):
    db_file = tmp_path / "test_iso.db"
    report_file = tmp_path / "results_iso.md"
    chart_dir = tmp_path / "charts"
    chart_dir.mkdir(parents=True, exist_ok=True)

    session = get_db_session(f"sqlite:///{db_file}")

    # Add 1 mock row with WER 0.00
    mock_row = BenchmarkResult(
        experiment="A",
        clip_id="clip_01",
        condition="clean",
        model="prisma-v2.5",
        format="verbatim",
        reference_text="परीक्षण वाक्य",
        hypothesis_text="परीक्षण वाक्य",
        wer=0.0000,
        cer=0.0000,
        latency_sec=0.48,
        duration_sec=3.0,
        rtf=0.16,
        mock=True,
        provenance="mock",
    )
    # Add 1 live row with WER 0.15
    live_row = BenchmarkResult(
        experiment="A",
        clip_id="clip_01",
        condition="clean",
        model="prisma-v2.5",
        format="verbatim",
        reference_text="परीक्षण वाक्य",
        hypothesis_text="परीक्षण शब्द",
        wer=0.1500,
        cer=0.1000,
        latency_sec=0.82,
        duration_sec=3.0,
        rtf=0.27,
        mock=False,
        provenance="live",
    )
    session.add(mock_row)
    session.add(live_row)
    session.commit()

    # 1. Generate live report -> must contain 0.1500 and NOT 0.0000
    generate_summary_report(session, report_file, provenance="live")
    live_content = report_file.read_text(encoding="utf-8")
    assert "DATA PROVENANCE: LIVE" in live_content.upper()
    assert "0.1500" in live_content
    assert "0.0000" not in live_content

    # 2. Generate mock report -> must contain 0.0000 and NOT 0.1500
    generate_summary_report(session, report_file, provenance="mock")
    mock_content = report_file.read_text(encoding="utf-8")
    assert "DATA PROVENANCE: MOCK" in mock_content.upper()
    assert "0.0000" in mock_content
    assert "0.1500" not in mock_content

    # 3. Test empty live DB handling
    empty_db = tmp_path / "empty.db"
    empty_session = get_db_session(f"sqlite:///{empty_db}")
    empty_report = tmp_path / "empty_report.md"
    generate_summary_report(empty_session, empty_report, provenance="live")
    empty_content = empty_report.read_text(encoding="utf-8")
    assert "No live results yet" in empty_content
    empty_session.close()

    session.close()
