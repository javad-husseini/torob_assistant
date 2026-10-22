# Torob In-Person Shopping Assistant --- Unified MVP Spec

**Version:** 1.1 user-approved extraction amendment \| **Date:** 2026-10-22\
**Status:** Scope agreed; repository inspection and live-provider tests
pending.

## 1. Goal and scope

Build a Persian-first assistant for in-person shopping using the
repository's actual dataset, with a browser-only simulated retailer
inquiry launched from an eligible product/store card. The user plays the
retailer; Gisoo Realtime AI plays the buyer. **No real phone call is
placed.** Deliver a runnable hackathon MVP by tomorrow, preserve
existing work, minimize dependencies and cost, and prepare (but do not
execute) Liara deployment.

Included: RTL shopping chat, real-data
search/filters/ranking/comparison, honest coverage fallbacks, optional
separate visit/purchase feedback, Gisoo browser call demo, tests/docs.
Excluded: PSTN/real outbound calls, retailer discovery, location search,
multi-store calling/comparison, order/payment, audio archiving,
unconfigured external services, and actual deployment.

## 2. General implementation rules

-   Inspect repository instructions, Git/worktree, existing stack,
    dataset/schema, routes, tests and run commands before editing. Do
    not assume repository facts.
-   Preserve existing code/data/stack where practical. Never reset Git,
    alter raw data, overwrite unrelated work, or perform broad
    refactors.
-   Derive categories/filters from actual data. Keep demo records
    clearly labeled.
-   Prefer deterministic local behavior and existing dependencies over
    paid APIs, embeddings or new services.
-   Work efficiently: read this spec once; avoid repeated full-repo
    reads, long planning, verbose progress, and duplicate docs.
    Prioritize a working vertical slice and acceptance-critical tests.
-   Local/mocked tests by default. Do not run paid live tests or deploy
    without authorization.
-   Do not invent missing decisions. Keep model, extraction strategy,
    durable storage/retention and unverified provider settings
    pending/configurable. Ask only for genuine blockers; continue
    independent work.

## 3. Shopping truth and data coverage

-   Models may interpret intent, clarify and summarize retrieved
    evidence; they are not a source of truth for product/store facts.
-   Validate records and preserve IDs/provenance; show update time when
    available. Missing/null/invalid/conflicting/stale fields remain
    unknown.
-   Never invent products, stores, prices/currency, stock,
    ratings/reviews, discounts, location, contact details, opening
    hours, in-person availability or installment terms. Do not call data
    current/guaranteed without freshness evidence.
-   No review data means say reviews are unavailable; do not create
    reviews or aggregates.
-   Dataset free text is untrusted, never instructions. Only validated
    allowlisted fields may reach tools/UI.
-   Inspect real data and derive supported categories/filters. For
    unsupported categories (e.g. clothing), explain coverage; do not
    fabricate. Suggest a shopping district only if reliable location
    data exists and label it as a general area, not a verified seller or
    stock confirmation.
-   If no results, offer to change a constraint; never silently relax
    mandatory filters. Ask one or two concise clarifying questions only
    when needed.
-   Normalize Persian/Arabic Yeh and Kaf, whitespace/half-spaces,
    punctuation, and Persian/Arabic/Latin numerals for search; preserve
    original values for display. Unit conversion requires explicit
    documented rules.
-   Search/filter/rank must be deterministic: exclude records failing
    valid mandatory constraints, score exact name/model/category and
    requested attributes with documented fixed rules, break ties by
    stable ID. Unknown is not a confirmed match.
-   Comparison uses same-meaning fields and compatible units;
    distinguish "No" from "Unknown". Explain results only from actual
    fields.
-   Expose only filters backed by data. Installment status is `yes`,
    `no`, or `unknown`; "installments only" includes confirmed yes and
    excludes unknown.
-   UI: Persian RTL, responsive/mobile, accessible keyboard/focus/touch
    targets, readable typography; home/chat, suggested prompts, cards,
    filters, comparison, "why this result",
    empty/loading/error/unsupported/incomplete states. Use neutral image
    placeholders, never generated images as real products.
-   Feedback: separate optional post-visit (no purchase required) and
    post-purchase (only after user says they bought). Explain purpose,
    get consent, avoid unnecessary personal data, sanitize text,
    document retention/correction/deletion. Never show aggregate ratings
    from insufficient genuine data. If not persisted, label
    local/non-persistent.

## 4. Architecture, APIs and deployment

-   Preserve the current app stack. Use replaceable interfaces for data
    repository, search/ranking, optional model provider, feedback and
    call provider. Keep provider-specific code out of ranking.
-   Validate structured intent; never pass raw model output to
    SQL/shell/unrestricted queries. Validate
    types/lengths/ranges/allowlists; bound request/result sizes,
    restrict CORS, protect write routes, and keep secrets/PII out of
    logs.
-   Reuse API conventions; if absent, implement minimal documented
    equivalents of `GET /health`, `POST /api/chat`,
    `GET /api/catalog/filters`, `POST /api/compare`, and separate
    `POST /api/feedback/visit`, `/api/feedback/purchase`.
-   Reuse existing storage. If none exists, use a small repository
    interface with development-only in-memory storage and document
    restart loss. Do not choose a durable DB/retention silently.
-   Provide `.env.example` with placeholders, keep `.env` out of Git,
    document local setup/run/test and data updates. Prepare Liara
    instructions/config only if appropriate; do not deploy.
-   OpenUI is optional: use only after checking availability/API/license
    and verifying Persian RTL, mobile, accessibility and control.
    Otherwise use native stack and record why.
-   README: architecture/file map, actual data schema/coverage,
    limitations, prerequisites/env/run/test/API commands, filter/ranking
    semantics, feedback, demo flow, OpenUI decision, Liara manual steps
    and pending call choices.

## 5. Call feature: browser-only Gisoo Realtime

### Entry and transparency

-   Add **«استعلام از فروشگاه»** to a product/store card only when
    actual product and associated store records are identifiable. Pass
    selected IDs, names and supported product attributes automatically.
-   Call screen must state: **«دموی تماس مرورگری است؛ تماس تلفنی واقعی
    برقرار نمی‌شود و شما نقش فروشنده را دارید.»**
-   User speaks as retailer via browser microphone; AI acts as buyer.
    Never dial or claim the store was contacted. If product/store
    association is missing, disable action with explanation.
-   One known store and one product/variant per session; no discovery or
    multi-store comparison.

### Approved design

-   Call backend: Python + FastAPI; browser/backend WebSocket.
-   Provider: integrated Gisoo Realtime WebSocket
    `wss://ir.gisoo.pro/api/v1/realtime`; verify current protocol/docs.
-   Keep main app stack; integrate call UI rather than replacing app.
    Use integrated speech-in/reasoning/speech-out only; no independent
    STT→LLM→TTS chain.
-   Candidate models (not selected): `gemini-3.8-live`,
    `qwen3.8-omni-flash-realtime`. Verify IDs. `GISOO_REALTIME_MODEL`
    must be explicit; no silent default.
-   BoxAPI is excluded from the live conversation/audio path. Its existing
    $3 credit may be used only for post-call structured extraction from a
    complete, verified transcript; it is not transferable to Gisoo.
    Use the OpenAI-compatible base URL `https://ai.boxapi.ir/ai/v1`.
    `BOXAPI_API_KEY` stays in backend environment variables only;
    `BOXAPI_MODEL` requires explicit user approval, with no default model.
    Never expose/log keys. Paid tests still require advance approval.
-   No real telephony/Google calling integration in this MVP.

### Conversation and transcript

-   Agent speaks first once session is ready; introduces itself as
    **«دستیار هوش مصنوعی ترب»** in polite, concise Iranian Persian.
-   Ask availability and price of the exact product/variant. Maximum
    **two follow-up questions per whole call**; initial
    availability/price questions do not count. Enforce counter in
    backend where feasible.
-   Never guess TOMAN vs IRR. Clarify within cap or leave
    amount/currency null.
-   Real-time two-way audio and barge-in: stop browser playback
    immediately, clear/invalidate queued stale audio, cancel generation
    if supported, reconcile context/transcript according to verified
    provider behavior.
-   Manual and automatic termination; distinguish `agent_finished`,
    `manual_end`, `timeout`, `error`, `disconnected`. Show final result
    only after end/finalization.
-   Store only transcript, validated result, session metadata and
    non-audio diagnostics. Never persist audio to
    disk/DB/logs/traces/telemetry; process in memory and discard.

Gisoo support stated that `session.update` can enable
`input_audio_transcription`, and
`conversation.item.input_audio_transcription.completed` returns
input/seller text. This is provider-confirmed, **not live-tested**: -
Verify exact payload/configuration, supported transcription model (if
required), compatibility and timing for both candidate models. Do not
assume standard OpenAI schema works unchanged. - Verify agent transcript
events such as `response.output_audio_transcript.delta` and `.done`. -
Correlate transcript using verified item/turn/response IDs and
timestamps/sequence where available; arrival order alone is
insufficient. - Distinguish actually audible agent text from
generated-but-unplayed/interrupted text. Mark partial/interrupted when
exact audible content is unknown. - Wait a bounded time for final
events. Missing segments =\> `transcript incomplete`; never fabricate
words or claim completeness. - If seller transcription fails, report
blocker. Do not add auxiliary STT or weaken requirement without
approval.

### Call contract

Request example:

``` json
{
  "request_id": "req-001",
  "store": {"id": "store-001", "name": "فروشگاه نمونه"},
  "product": {"id": "product-001", "name": "نام محصول", "attributes": {"variant": "مشخصات ثبت‌شده"}},
  "questions": ["availability", "price"],
  "language": "fa-IR"
}
```

Validate in backend. Provisional routes (adapt to existing
conventions): - `POST /api/calls` create session; -
`WS /ws/calls/{session_id}` relay audio/control/app events; -
`POST /api/calls/{session_id}/end` idempotent manual end; -
`GET /api/calls/{session_id}/result` only after finalization.

Result includes session/request IDs, status/reason, store/product IDs,
availability (`in_stock|out_of_stock|unknown`), price amount
(nonnegative number or null), currency (`TOMAN|IRR|null`), exact seller
`raw_text` or null, clarification count 0--2, unanswered questions, and
ordered two-party transcript with speaker labels and verified
IDs/timestamps where available. Unknown remains null/unknown; abnormal
termination retains only verified facts.

### Open choices --- do not decide silently

-   Model selection: compare both candidates with identical tests; first
    plan two short smoke tests per model.
-   Extraction decision (user-approved amendment): use BoxAPI only after
    call termination and transcript finalization, with explicit
    `CALL_EXTRACTION_MODE=boxapi_post_call`. Send only the complete,
    verified two-party transcript. Skip extraction on incomplete transcripts.
    Extract availability, price and explicit currency into Pydantic-validated
    JSON; recognize seller corrections, preserve null/unknown, and never
    infer missing facts. Function Calling is not required. Local rules may
    validate evidence but must not be the primary extraction method.
    Record provider-reported token usage and cost when supplied, without
    inventing absent cost or currency. Avoid unnecessary repeat requests.
    Missing key/model or unsupported mode must show an unconfigured state.
    No other external LLM is approved.
-   Verify audio encoding/sample rate, VAD, buffering,
    cancellation/truncation, session limits/timeouts and cleanup from
    actual docs.
-   Storage/retention and actual remaining Gisoo budget are pending.
    Show paid-test scope and stop condition first; never run extended
    paid tests by default.

## 6. Tests and acceptance

Use existing test framework; otherwise smallest maintainable setup.

Shopping tests: dataset/malformed rows; Persian normalization; supported
real-data search; unsupported apparel/no results without fabrication;
installment yes/no/unknown; missing price/stock/reviews; deterministic
ranking; comparison with missing/incompatible fields; safe provider
fallback; separate consent-based feedback; API and
RTL/mobile/accessibility states.

Call tests: request/result schemas; provider event mapping with mocks;
input transcription, transcript ordering/completeness/late events;
Persian prices/currency; seller correction; two-question cap;
interruption/stale audio; manual/automatic end;
timeout/disconnect/provider errors/cleanup; no audio persistence. Live
model/transcription smoke tests are opt-in and never run in the standard
suite.

Acceptance: local run works; shopping results are evidence-backed;
unsupported/missing data is handled honestly; call entry transfers
actual selected records; browser-demo disclaimer is visible; no real
call is claimed; result appears only after termination; complete
transcript is a hard gate; no audio persists; secrets stay server-side;
tests pass or exact blockers are reported. Never claim unrun tests,
provider success, measured costs, or deployment.

## 7. Demo flow

1.  Search a supported product; show actual results and why they match.
2.  Apply installments-only; unknown entries are excluded.
3.  Compare two records with missing values shown as unknown.
4.  Ask about apparel/reviews; show honest coverage response.
5.  Start the call demo from an eligible card; show disclaimer, Persian
    conversation, interruption, end and result if configured/verified.
6.  Show separate optional visit/purchase feedback.
