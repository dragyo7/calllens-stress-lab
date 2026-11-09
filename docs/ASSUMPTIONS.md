# ASSUMPTIONS

Update each item to verified / unverified / wrong and add evidence.

- [verified] Omitting model selects Prisma v2.5; `prisma-v3.0` is opt-in. Evidence: `gnani.stt._prisma.is_prisma_v3(model)` returns True only for "prisma-v3.0"; omitting model defaults to v2.5.
- [verified] Prisma v2.5 and v3.0 share at least one explicit output format. Evidence: `gnani.stt._prisma.check_format()` confirms both models support "verbatim" and "transcribe".
- [verified] Installed SDK exposes the methods and signatures expected by the brief. Evidence: `inspect.signature` on `GnaniSTTClient.transcribe` and `GnaniTTSClient.synthesize`.
- [verified] STT accepts mono PCM16 at 16 kHz and has a 30-second request limit. Evidence: `GnaniSTTClient.transcribe` docstring and `SAMPLE_RATE_16K`.
- [unverified] FLEURS `hi_in` files and TSV columns match expected paths/fields (pending M2).
- [verified] A suitable Hinglish or Hindi voice is available in Timbre v2.5. Evidence: `GnaniTTSClient.supported_voices(model="timbre-v2.5")` returns 42 voices (including 'Pranav'), with `SUPPORTED_TTS_LANGUAGES` containing 'hi-IN'.
- [unverified] The selected output format returns numeric entities in a form supported by the extractor (pending M2 pilot).
- [unverified] API credit cost per request (pending G1 probe).
- [verified] Antigravity automatically loads `.agents/rules/calllens.md`. Evidence: active workspace rules confirmed loaded.
