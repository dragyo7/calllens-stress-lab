# CallLens Stress Lab — Project Brief

**Status:** authoritative source of truth  
**Target:** a reproducible, honest benchmark and small demo for the Great Indian Internship Challenge by Gnani.ai.  
**Core comparison:** Gnani Prisma v2.5 vs Prisma v3.0 on Hindi speech under clean and simulated-telephony conditions.

## 1. Role and working style

Act as a senior Python engineer. Inspect before changing. Work in small verified milestones. Be concise; prioritize a working, reproducible result over feature breadth. Do not claim completion without command output or other direct evidence.

## 2. Hard constraints

1. Never open, print, echo, copy, edit, stage, or commit `.env` or secret values. The application may load `GNANI_API_KEY` through `python-dotenv`; do not inspect the file. Never ask the user to paste the key into chat or a prompt.
2. Every Gnani API request must pass through `calllens/gnani_client.py::call`. No direct client calls elsewhere.
3. Use public or synthetic data only. Do not use `datasets.load_dataset` or `trust_remote_code`.
4. Approved dependencies only: `gnani-vachana`, `jiwer`, `numpy`, `scipy`, `soundfile`, `huggingface_hub`, `sqlalchemy`, `fastapi`, `uvicorn`, `python-dotenv`, `matplotlib`, `pytest`, `httpx`, `pydantic`. Ask before adding anything else.
5. Allowed network hosts: `api.vachana.ai`, `huggingface.co` and its CDN subdomains, `pypi.org`, `files.pythonhosted.org`. Do not browse or download from other hosts.
6. Use the Python version already installed (Python 3.10+). Use `pathlib`; scripts must work in Windows PowerShell and Linux/macOS. No ffmpeg; implement mu-law with NumPy.
7. Live API calls are prohibited except at G1, G2, and G3. At each gate: print the exact planned calls by script/model/operation, state the maximum, and STOP. Wait for the user's explicit `go`. Any other reply is an instruction, not approval.
8. Set `MAX_LIVE_CALLS` to the planned number plus 10% (round up) for that gate. Reset the gate budget only when the user explicitly approves the next gate. Cache hits do not count as live calls. Retries do count as actual network attempts and must be logged separately; never hide them.
9. Never delete user data, cache, or existing files. Never use destructive commands, disable tests, or run `git push`.
10. Maximum three fix attempts per failure. Then stop, record the blocker in `docs/HANDOVER.md`, and report it.
11. Commit once per passing milestone. Before committing, show `git status --short`; verify no `.env`, key, dataset, audio, cache, or database is staged.
12. Record assumptions as verified/unverified/wrong in `docs/ASSUMPTIONS.md`. Update `docs/HANDOVER.md` after each milestone using the five headings: Done / In progress / Broken or risky / Next / Do not touch.
13. If a milestone cannot meet its done criteria, do not fake it. Continue to documentation with the gap clearly listed as a limitation.
14. Never fabricate results, citations, API behavior, benchmark metrics, screenshots, test output, or resume claims.

## 3. Goal and honest claim

Build a small, reproducible benchmark of Prisma v2.5 vs v3.0 for Hindi read speech under simulated telephony degradation, plus a Stress Lab demo. The README must report measured results, sample sizes, confidence intervals, limitations, and reproduction steps.

This is **not** a benchmark on real customer calls. It uses read speech and simulated channel effects. State this prominently.

## 4. Layout

Create and maintain this layout:

```text
calllens/
  .agents/rules/calllens.md
  .env.example
  .gitignore
  requirements.txt
  README.md
  calllens/
    __init__.py
    gnani_client.py
    degrade.py
    metrics.py
    extract.py
    benchmark.py
  scripts/
    usage_probe.py
    get_fleurs.py
    gen_noise.py
    gen_utterances.py
  tests/
  app/
    main.py
    static/index.html
  docs/
    BRIEF.md
    CHECKS.md
    HANDOVER.md
    DECISIONS.md
    ASSUMPTIONS.md
    THREAT.md
    FAILURE.md
    DATA.md
    ROLLBACK.md
  tests/results.md
```

Dataset and generated audio must live outside the Git repository. Default `DATA_DIR` to the sibling directory `../calllens-data`, overridable by environment variable. Do not move or delete existing user files.

## 5. Gnani client discovery and API rules

Before implementing API calls, install/inspect the official `gnani-vachana` package and pin the exact installed version in `requirements.txt`. Do not guess SDK method signatures.

Print and preserve evidence for:
- `inspect.signature(GnaniSTTClient.transcribe)`
- the actual TTS synthesis method signature
- `GnaniSTTClient.supported_languages()`
- `GnaniTTSClient.supported_voices(model="timbre-v2.5")`

If the package/API differs from this brief, stop and report the actual interface before adapting code.

Model behavior:
- Omitting `model` is documented as Prisma v2.5; Prisma v3.0 is opt-in with `model="prisma-v3.0"`. Verify against the installed SDK/docs.
- Always pass the same explicit output format to both models **if both models support it**.
- If v2.5 does not support the selected explicit format, do not silently compare unlike settings or claim a controlled comparison. Record the incompatibility, test what is supported, and clearly label the comparison as non-equivalent or stop that experiment.
- STT input must be mono PCM16 at a supported sample rate, 8–44.1 kHz, and no longer than 30 seconds. Normalize/resample all audio to 16 kHz mono PCM16 before STT.
- Measure actual credit consumption at G1. Cost per call is initially unknown.

All requests go through `gnani_client.call(kind, payload)`. It must provide:
- deterministic SHA-256 cache key over audio/content plus model, language, format, voice, and relevant parameters;
- cache successful responses only;
- live-call cap controlled by `MAX_LIVE_CALLS` (default 10);
- concurrency limit 2;
- bounded exponential backoff for 429/5xx;
- 30-second request timeout where supported;
- redacted logs (never log API keys or authorization headers);
- clear distinction between logical calls, cache hits, retries, and actual network attempts.

Tests must prove cache hits make no network request, the cap blocks call N+1, failures are not cached, and retry behavior is bounded.

## 6. Dataset and synthetic test data

Use FLEURS Hindi India (`hi_in`) through `huggingface_hub`, not `datasets.load_dataset`. Expected files are `data/hi_in/test.tsv` and `data/hi_in/audio/test.tar.gz` (archive size is approximate and may change).

Before extraction:
- print the first three TSV rows and actual column names;
- verify the actual transcript and audio-path columns rather than assuming names;
- inspect archive members safely;
- select 30 clips no longer than 28 seconds using actual sample rate/sample count;
- extract only selected clips into the external data directory;
- write a manifest with stable clip IDs, transcript, path, duration, sample rate, and source attribution.

Do not assume the archive layout. Validate paths and prevent path traversal during extraction. If source files or columns differ, document the observed structure and adapt safely.

Experiment D: generate 20 five-second clips locally with NumPy: 10 seeded white-noise clips and 10 silence clips.

Experiment F: create 10 short Hinglish BFSI template utterances with amount, due day, and name. Use one Timbre v2.5 voice returned by `supported_voices`; prefer Hinglish if actually available, otherwise use a supported Hindi voice and record the choice. Store ground truth separately. These are synthetic and voiced by TTS, not human recordings.

## 7. Audio conditions

Apply transformations in this order:
- `clean`: original normalized 16 kHz clip.
- `tel`: band-limit to 300–3400 Hz, resample to 8 kHz, apply mu-law encode/decode round trip, then return to 16 kHz for STT.
- `tel_snr10`: add deterministic white Gaussian noise at 10 dB SNR, then apply the telephony chain.
- `tel_snr0`: add deterministic white Gaussian noise at 0 dB SNR, then apply the telephony chain.

Noise must be seeded by clip ID. Measure SNR against whole-clip RMS and test at least three signals. Target measured SNR tolerance is ±0.5 dB. Document the precise implementation order and any deviations.

## 8. Metrics

- WER = (substitutions + deletions + insertions) / reference word count, using `jiwer`.
- CER likewise at character level.
- Normalize consistently: Unicode NFC, strip punctuation, collapse whitespace. Preserve a raw transcript alongside normalized text.
- FLEURS reference must come from the verified raw-transcription column.
- Experiment D false-text rate = proportion of noise-only/silence clips producing any non-whitespace transcript.
- Experiment F entity accuracy: exact match for amount (integer rupees) and due day, reported separately by field and utterance. Extractor supports digits and lakh/crore/लाख/करोड़/हज़ार forms. If the chosen ASR output format spells numbers as words, report the limitation; do not silently add word-number parsing.
- Latency: client wall-clock time; report p50 and p95. RTF = wall-clock time / audio duration.
- Confidence intervals: bootstrap over clips, 1,000 resamples, seed 0. Report N in every results table and explain the resampling unit.
- Never treat a small pilot as statistically conclusive. Show raw counts alongside rates where possible.

Required extractor examples:
- `2.25 lakh` -> 225000
- `3,50,000 rupees` -> 350000
- `₹2.25 crore` -> 22500000
- `5 तारीख तक` -> due_day 5
- reference `a b c`, hypothesis `a x c` -> WER 0.333...

## 9. Milestones

### M0 — Scaffold and environment
Verify the supplied scaffold. Create `requirements.txt`, package folders, tests, app folders, and a Python virtual environment only if absent. Do not overwrite user files. Verify Python and Git versions. Commit only after safe status review.

### M1 — Gnani client and usage probe
Implement `calllens/gnani_client.py` and unit tests. Add `scripts/usage_probe.py` with mock mode by default. `--live` performs exactly four logical calls: v2.5 and v3.0 on two short clips, routed through the client. Before G1, show the exact plan and wait. After approval, run and report measured latency, output differences, retries/network attempts, and credit usage if the user supplies it.

**G1:** no live calls until explicit `go`.

### M2 — Data preparation and format pilot
Implement FLEURS download/validation, safe selective extraction, noise generation, and TTS utterance generation. `gen_utterances.py --dry-run` must show intended TTS calls without making them. Run a 10-clip v3.0 format pilot across formats actually supported by the SDK. Calculate the exact number of calls as `10 × number_of_tested_formats` (unless the user approves a different design). Print the full plan, including the 10 TTS calls, then stop at G2. If no valid format is shared by v2.5 and v3.0, record the comparison limitation.

**G2:** no live calls until explicit `go`.

### M3 — Signal processing and metrics
Implement `degrade.py`, `metrics.py`, and `extract.py`. Add tests for required examples plus at least 10 edge cases; list them for review. Verify SNR tolerance on three signals. No live calls.

### M4 — Benchmark
Implement resumable benchmark with SQLite via SQLAlchemy. `--dry-run` must print per-experiment logical calls, expected cache hits, and estimated live calls:
- A: 30 clips × 4 conditions × 2 models = 240 STT logical evaluations.
- D: 20 noise/silence clips × 2 models = 40.
- F: 10 TTS utterances × 4 conditions × 2 models = 80.
- Full uncached total: 360 logical STT evaluations (TTS generation is separately counted and cached).

Persist inputs, model/configuration, raw outputs, metrics, timing, cache status, and errors. Generate `tests/results.md` and PNG charts: WER by condition with CIs; WER versus p95 latency. Include N and configuration in every table/chart caption. Keep raw results reproducible.

**G3:** first print the dry-run and exact live-call plan. On user `go`, run only `--scale 0.1`, report actual calls and results. Ask for a second explicit `go` before `--scale 1`. Never start full scale automatically. If credit budget is insufficient, stop with partial results.

### M5 — Stress Lab demo
Build FastAPI and a single HTML page. `POST /api/stress` accepts a clip ID and condition and returns both model transcripts, WER, entity checks where applicable, and latency. Mock/cached mode is default. Live mode requires explicit `?live=1` and still passes through the cap.

Enforce:
- upload limit 5 MB if uploads are supported;
- audio duration limit 30 seconds;
- 10 requests/minute/IP if rate limiting is implemented;
- validate content type and audio decoding; do not trust filename or extension.

UI: clip picker, condition selector, side-by-side transcripts, entity checklist, clear mock/live indicator. Do not claim production-grade security. Ask before installing Playwright; if approved and feasible, save screenshot under `docs/`.

### M6 — Documentation and release
Create:
- `README.md`: measured results table, chart and screenshot if available, architecture diagram, exact reproduction commands, environment setup, limitations, FLEURS CC BY 4.0 attribution.
- `docs/THREAT.md`: anonymous uploader, credit-burning scraper, malicious audio, leaked key, compromised dependency. Every mitigation claim cites file:line or says `NOT IMPLEMENTED`.
- `docs/FAILURE.md`: Gnani slow/429/down, exhausted credits, 30-second limit, DB error; behavior and detection. Every claim cites file:line or says `NOT IMPLEMENTED`.
- `docs/DATA.md`: schema, sizes, source, retention, why SQLite.
- `docs/ROLLBACK.md`: safe rollback and recovery steps.

Do not create `docs/DEFENSE.md`. Do not tag v1.0 unless all release criteria are met; otherwise use a clearly labelled prerelease tag or no tag and explain why.

## 10. Resume integrity

Only recommend resume metrics that are actually measured, reproducible, and supported by the saved database and `tests/results.md`. Include exact N, model/configuration, conditions, and date. Never invent improvements, percentages, user counts, or production readiness. If results are incomplete, recommend a truthful project description focused on engineering work rather than benchmark claims.

## 11. Final report

Report:
- milestones completed / incomplete;
- exact pytest summary and command;
- `git log --oneline`;
- actual live calls, retries, and cache hits by gate;
- benchmark sample sizes and results, if any;
- open blockers and limitations;
- exact next action for the user.
