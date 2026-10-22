# Verification — 2026-10-22

- `.\.venv\Scripts\python -m pytest -q`: **82 passed**, 38.09 seconds. Includes full CSV loading/search, schema validation, feedback consent/ownership, provider PCM relay mocks, transcript linkage and missing speech, interruption/stale acknowledgements, extraction schema/evidence/corrections, usage retention, no request for incomplete transcripts, missing-model configuration, and no duplicate extraction attempts, same-turn seller corrections, malformed response envelopes, and mocked timeout/disconnect cleanup.
- One upstream warning: Starlette TestClient deprecates the current httpx integration in favor of httpx2. Tests pass; production extraction uses httpx directly.
- `node --check static/app.js`, `node --check static/capture.js`, `python -m compileall -q app`: passed.
- Local Chrome browser checks: real search, selection/comparison, browser-call disclaimer and unconfigured state, purchase confirmation, feedback creation/deletion, installments unknown exclusion, review fallback, RTL and 390px mobile width passed. Screenshots: desktop.png/mobile.png. These checks never start a provider call.
- `python -m docs.audit_data`: actual counts/hashes saved in data-report.json; accepted 225803 products, 331401 offers, 6476 stores, 3428 categories. Load 30.22 seconds in that run.
- Local HTTP `/health` and shopping flows verified. Server startup has to rebuild the in-memory catalog.

Not verified: paid Gisoo or BoxAPI access, actual account balances, model quality/latency/cost, microphone hardware playback, provider-specific seller/agent transcription and item linkage, full recovery after interruption, Docker build, Liara deployment. No paid model request or deployment was run. Qwen interruption is deliberately reported as unsupported/incomplete rather than continuing with unplayed model history. Real speech question-count enforcement still requires the planned opt-in smoke tests.

Models explicitly configured in local .env after user delegation: Gisoo qwen3.8-omni-flash-realtime; BoxAPI gpt-6-luna. Main extraction is BoxAPI post-call only; local rules validate evidence only. Keys are not included. Protocol verification flag stays false pending model-specific opt-in checks. Durable storage/production retention remain undecided; only documented in-memory development repositories are used.

