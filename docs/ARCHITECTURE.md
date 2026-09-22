# Architecture, decisions and boundaries

## Request flow

`FastAPI boundary -> Pydantic envelope -> BotService -> SQLite transaction ->
context lookup -> planner -> policy gates -> API response + committed state`.
No runtime inference API, random sampling, scraping, or per-request network I/O.
The composer consumes received facts, not the bundled expanded dataset. Bundled
examples are developer fixtures, not a database preloaded into the deployed bot.

## State and determinism

Contexts use `(scope, context_id)` keys; versions replace whole payloads atomically.
A duplicate version returns the original acknowledgment even if its repeated
payload differs. Lower versions return 409. Context version is authoritative;
`delivered_at` is not used as a substitute version counter. SQLite WAL mode,
serialized transactions and a busy timeout protect the local single-instance
state. One Uvicorn worker/one replica is the supported deployment shape.

Standalone `compose` is deterministic for identical input and optional explicit
`now`. HTTP planning uses the supplied simulation timestamp; storage/uptime use
real time. Identical input *and prior state* produces identical decisions. A
repeated tick after committing a send deliberately returns no repeated action.
Reply retries with identical conversation/turn/payload return cached responses;
changed content for the same turn conflicts. This is not a guarantee that every
HTTP response byte is globally deterministic (uptime and stored timestamps differ).

Commit-before-response gives at-most-once action scheduling, not exactly-once
external delivery. The contract has no delivery-ack API; a lost HTTP response may
therefore lose an action rather than resending it. Suppression keys and body hashes
are recipient-scoped, not globally shared across all merchants.

## Planning and grounding

Trigger urgency plus signal fit determines ordering. One recipient gets at most
one action per tick, with a hard overall cap of 20. Missing contexts, mismatched
customer ownership, future due dates, expired triggers, STOP, absent consent,
repeated content and cadence can suppress sends. Normal cadence defaults to 30
minutes; max three unanswered sends. Some time-sensitive alerts bypass the
ordinary gap but not consent/STOP/caps. Novel events with an explicit headline can
be discussed without inventing facts; unsupported empty events are suppressed.

Category offers are examples, never assumed active for a merchant. Merchant offer
status and validity are checked. Source headlines/citations are attributed as
provided; the synthetic research content is not independently validated medical
advice. Performance windows are kept distinct; missing window metadata is not
silently called a 30-day snapshot. A lower CTR benchmark is not proof of causality.
No fabricated competitors, counts, offer inclusions, slot inventory or discounts.

English and Hinglish are supported. Facts retain original terminology. Other
regional-language preferences currently fall back to English rather than a
pretended fluent translation. Category-specific language is rule-based, not a
complete general-purpose translation or domain-reasoning model.

## Customer consent, session and identity

Customer outreach requires explicit purpose-specific consent and a compatible
channel; missing consent fails closed. Identity/merchant ownership is checked.
Customer-directed actions use `merchant_on_behalf`; merchant-directed actions use
`vera`. Shared-channel healthcare copy minimizes treatment/medication disclosure.
Consent to appointment reminders is not automatically marketing consent.

Only a real human inbound message within 24 hours opens the free-form window.
Auto-reply history does not. Outside the window, the rendered output matches the
registered template plus its parameters. `templates.json` mirrors
`vera/templates.py`. These are challenge-simulated template structures, not
Meta-approved real WhatsApp templates. There is no delivery connector.

## Reply handling

Priority handling covers opt-out, hostile/off-topic input, automated replies,
backoff, onboarding intent, grounded pricing, acceptance and requests for detail.
Acceptance supplies a draft/checklist; it does not reopen the original sales pitch.
No action is reported complete without an actual external integration. Cached
retries do not duplicate transitions. New context is resolved again before an
accepted draft so stale offers/research are not silently reused. STOP survives
conversation closure and later history truncation within the evaluation state.

Unknown conversation IDs can initialize replay state only with a known valid
participant, supporting the supplied simulator's standalone replay tests. They
are not treated as permission to read arbitrary other recipients' conversations.

## Security and retention

Envelope validation, raw request-size limits, parameterized SQL, ownership checks
and optional Bearer authentication are provided. Request bodies/messages are not
sent to external services or logged by the application. Access logging is off by
default. The optional scorer is separate and may transmit context to its provider.

Default unauthenticated writes match the submission flow, but do not provide a
production tenancy or abuse boundary. Use one isolated synthetic-data evaluation
instance. A configured `API_TOKEN` protects writes; `TEARDOWN_TOKEN` can separately
protect reset. Health and metadata remain public. No rate limiter is enabled that
could reject the judge's expected traffic; host-level protection is a deployment
responsibility.

`POST /v1/teardown` deletes application state, checkpoints the WAL and vacuums the
DB. The default 24-hour inactivity expiry is lazy/request-driven, not a scheduled
guarantee. Erasure of host snapshots/backups is outside this application. Horizontal
scaling/shared-service production use needs a separate durable DB and tenancy
redesign, not simply more app replicas.
