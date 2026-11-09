# DECISIONS

Append new decisions at the bottom using: context / options / chosen / why / revisit if.

- D-001: Use the official `gnani-vachana` SDK rather than raw REST unless a required capability is missing. Revisit if the SDK cannot support the required request.
- D-002: Load FLEURS source files through `huggingface_hub`; do not use `datasets.load_dataset` or remote code.
- D-003: Use SQLite through SQLAlchemy for a reproducible local benchmark with no database service setup.
- D-004: Use deterministic synthetic noise and simulated telephony rather than real customer calls; this protects privacy and improves reproducibility but limits external validity.
- D-005: Normalize every STT input to mono PCM16 at 16 kHz before calling the API.
- D-006: Use one explicit output format across both models only if both support it. Otherwise label the comparison non-equivalent or stop the controlled comparison.
- D-007: Format selection is pending the M2 pilot; record evidence and rationale before benchmarking.
- D-008: Use Python 3.12 in `.venv` with exact pinned versions of the 14 approved dependencies (`gnani-vachana==0.9.0`, etc.) to guarantee reproducibility.

