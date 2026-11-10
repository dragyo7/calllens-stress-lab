# CallLens — Independent QA Checklist

Run in a new Antigravity conversation after the build. Read `docs/BRIEF.md`, `docs/HANDOVER.md`, `docs/ASSUMPTIONS.md`, `docs/DECISIONS.md`, `tests/results.md`, and relevant source files first. Do not trust prior claims. No live API calls without a fresh explicit `go`. Reuse cache; never rerun the full benchmark.

## Checks

1. **Hygiene:** inspect Git status and history for secrets; verify `.gitignore`; verify no `.env` contents were exposed; no `datasets.load_dataset` or `trust_remote_code`; confirm datasets/audio are outside repo.
2. **API routing:** search all Gnani SDK use; prove all calls route through `gnani_client.call`; prove cache hits do not make network requests and live cap blocks N+1.
3. **Audio contract:** prove every STT input is mono PCM16, 16 kHz, <=30 seconds; show tests and actual call payload metadata. Do not make a live call for this check.
4. **Model comparison:** show selected format and evidence that both models support it. If not, ensure results are labelled non-equivalent and no apples-to-apples claim is made.
5. **Tests:** run `pytest -q`; paste real summary. Investigate every failure; maximum three fix attempts per failure.
6. **Metric sanity:** show three FLEURS examples with reference, hypothesis, WER; hand-check WER cases; verify SNR on three signals; show N and confidence intervals; investigate if degradation does not generally worsen WER.
7. **Benchmark integrity:** independently recompute every published result from SQLite; compare logical calls, actual network attempts, retries, and cache hits; verify bootstrap seed and resampling unit.
8. **Adversarial limitations:** list at least five ways results may mislead (normalization, format differences, simulated telephony, small N, TTS-generated F data, read-speech domain). Run the two cheapest checks without live calls.
9. **App:** test mock default, upload validation, 5 MB limit if uploads exist, >30-second audio rejection, and rate limit if implemented. Do not send 11 requests if that would create external side effects; local mock requests are acceptable. Confirm screenshot only if one was actually generated.
10. **Docs/release:** verify README limitations and FLEURS attribution; spot-check file:line claims in THREAT.md and FAILURE.md; ensure no `docs/DEFENSE.md`; verify tag/release claims match actual state.

## Output

Provide a table with check, PASS/FAIL, and one-line evidence. Then list remaining risks, exact measured results safe for a resume (with N and configuration), and manual tasks remaining: prepare the defense document, record the demo video, publish the project/social post, and submit the challenge form. Never invent results.
