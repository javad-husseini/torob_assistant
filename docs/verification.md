# Verification — 2026-10-22

- `.\.venv\Scripts\python -m pytest -q`: **83 passed**, 40.23 seconds. Includes full CSV loading/search, schema validation, feedback consent/ownership, provider PCM relay mocks, transcript linkage and missing speech, interruption/stale acknowledgements, extraction schema/evidence/corrections, usage retention, no request for incomplete transcripts, missing-model configuration, and no duplicate extraction attempts, same-turn seller corrections, malformed response envelopes, and mocked timeout/disconnect cleanup.
- One upstream warning: Starlette TestClient deprecates the current httpx integration in favor of httpx2. Tests pass; production extraction uses httpx directly.
- `node --check static/app.js`, `node --check static/capture.js`, `python -m compileall -q app`: passed.
- Local Chrome browser checks: real search, selection/comparison, browser-call disclaimer and unconfigured state, purchase confirmation, feedback creation/deletion, installments unknown exclusion, review fallback, RTL and 390px mobile width passed. Screenshots: desktop.png/mobile.png. These checks never start a provider call.
- `python -m docs.audit_data`: actual counts/hashes saved in data-report.json; accepted 225803 products, 331401 offers, 6476 stores, 3428 categories. Load 30.22 seconds in that run.
- Local HTTP `/health` and shopping flows verified. Server startup has to rebuild the in-memory catalog.

Not verified: paid Gisoo or BoxAPI access, actual account balances, model quality/latency/cost, microphone hardware playback, provider-specific seller/agent transcription and item linkage, full recovery after interruption, Docker build, Liara deployment. No paid model request or deployment was run. Qwen interruption is deliberately reported as unsupported/incomplete rather than continuing with unplayed model history. Real speech question-count enforcement still requires the planned opt-in smoke tests.

Models explicitly configured in local .env after user delegation: Gisoo qwen3.8-omni-flash-realtime; BoxAPI gpt-6-luna. Main extraction is BoxAPI post-call only; local rules validate evidence only. Keys are not included. Protocol verification flag stays false pending model-specific opt-in checks. Durable storage/production retention remain undecided; only documented in-memory development repositories are used.



## shadcn UI redesign verification

- `cd frontend; npm.cmd run build`: TypeScript 7 and Vite 8 production build passed. React/shadcn components come from the official CLI, with Nova/Radix, RTL, local Vazirmatn font and Lucide icons. Output is served by the existing FastAPI process at `/`.
- `.\.venv\Scripts\python tests/browser_check.py`: passed in local Chrome at 1440px and 390px. Covers light/dark themes, searchable categories, real-data search, selecting/comparing records, accessible dialogs, consent/purchase feedback and deletion, mobile Sheet filters, no-result/review states, no horizontal overflow, and no browser console errors. The test blocks call creation, so it cannot start a paid provider session.
- The new API test verifies per-document style nonces match the built HTML and differ between requests. Radix scroll-lock styling works without adding unsafe-inline to CSP; script-src remains self.
- Full suite after redesign: **83 passed**, one upstream Starlette/httpx deprecation warning, 40.23 seconds. Legacy sandbox-owned test folders were left intact; temporary test files now use `.test-tmp`, cache uses `.test-cache`.
- Configured backend credential values were checked against built frontend files without printing them; no values were found in the build.
- `npm audit --omit=dev`: zero runtime dependency vulnerabilities. Seven high-severity development-only advisories remain in the official shadcn CLI dependency tree (braces/fast-glob); compatible audit fixes were unavailable and no forced downgrade was applied. Node/CLI are excluded from the final Python runtime image.
- Screenshots: `ui-home.png`, `ui-dark.png`, `desktop.png`, `mobile.png`, `ui-mobile-filtered.png`.
- No paid calls, live BoxAPI extraction, Docker build, deployment, commit or push was performed for this redesign. Existing live-provider limitations still apply.
