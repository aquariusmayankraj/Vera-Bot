# HTTP API guide

Base URL examples below use a local server. Use HTTPS on the submitted public
host. JSON is UTF-8. Request body cap is 500 KiB. Open `/docs` for the generated
OpenAPI schema. Health and metadata are open; optional `API_TOKEN` requires
`Authorization: Bearer <token>` for writes. No default token is configured.

## Minimal end-to-end request sequence

Run from the backend folder with the server running. These files contain explicit
**synthetic April 26, 2026 simulation time**, not today's date. Do not change only
one timestamp: event expiry and incoming times must remain coherent.

```bash
curl -sS http://127.0.0.1:8080/v1/healthz
curl -sS http://127.0.0.1:8080/v1/metadata
curl -sS http://127.0.0.1:8080/v1/context -H 'Content-Type: application/json' --data-binary @examples/context_category.json
curl -sS http://127.0.0.1:8080/v1/context -H 'Content-Type: application/json' --data-binary @examples/context_merchant.json
curl -sS http://127.0.0.1:8080/v1/context -H 'Content-Type: application/json' --data-binary @examples/context_trigger.json
curl -sS http://127.0.0.1:8080/v1/tick -H 'Content-Type: application/json' --data-binary @examples/tick.json
```

Copy the returned `conversation_id` into `examples/reply.json`, then:

```bash
curl -sS http://127.0.0.1:8080/v1/reply -H 'Content-Type: application/json' --data-binary @examples/reply.json
```

For another turn update message, advance `received_at` and increment `turn_number`.
Repeating the identical request replays the cached response. A repeated tick does
not send the same trigger twice; use the unique-ID smoke-test script for repeated
tests without manually editing demo IDs. Do not mix demos into official evaluation.

## POST /v1/context

Envelope: `scope` (`category`, `merchant`, `customer`, `trigger`), `context_id`,
integer `version >= 1`, object `payload`, timezone-aware `delivered_at`. Source
payloads are flexible JSON; missing semantics are guarded when planning.

Success: `{"accepted":true,"ack_id":"ack_...","stored_at":"...Z"}`.
Same scope/ID/version: exact prior acknowledgment, no replacement. Higher version:
whole-object atomic replacement. Lower version: 409 with `reason: stale_version`
and `current_version`. Present context payload identifiers must agree with their envelope; absent ones are filled from context_id.

## POST /v1/tick

Envelope: `{"now":"2026-04-26T10:00:00Z","available_triggers":["trigger_id"]}`.
Triggers must already have been pushed. Response: `{"actions":[...]}`. Up to 20
new-conversation actions; an empty array is valid. Each action contains:

```json
{
  "conversation_id": "conv_generated_by_server",
  "merchant_id": "demo_cafe",
  "customer_id": null,
  "send_as": "vera",
  "trigger_id": "demo_calls_dip",
  "template_name": "vera_context_message_v1",
  "template_params": ["the grounded composed message"],
  "body": "Vera update: the grounded composed message",
  "cta": "binary_yes_no",
  "suppression_key": "demo:calls:week1",
  "rationale": "why this action was selected"
}
```

The text above describes the fields, not a fixture asserted as actual output.
Within a valid human-reply session, `template_name` is null and params are empty.
Customer actions use `merchant_on_behalf` and the matching customer ID.

## POST /v1/reply

Use the returned conversation ID, merchant/customer identifiers, `from_role`
(`merchant` or `customer`), `message`, timezone-aware `received_at`, and positive
integer `turn_number`. The API returns one of:

```json
{"action":"send","body":"the actual reply/draft","cta":"none","rationale":"..."}
```
```json
{"action":"wait","wait_seconds":1800,"rationale":"..."}
```
```json
{"action":"end","rationale":"..."}
```

A supplied participant must own the conversation. Replayed turns with changed
content conflict. STOP is persisted at recipient level, not just current thread.
A new conversation ID is accepted for a known participant for isolated simulator
replay, but cannot bypass ownership of an existing conversation.

## GET /v1/healthz and GET /v1/metadata

Health: status, uptime seconds, counts for all four context scopes. It exercises
SQLite rather than merely returning a constant. Metadata: team name/members,
model description, approach, contact email, version and submitted timestamp.
Set your own team/contact environment values before submission.

## Lifecycle and errors

`POST /v1/teardown` clears challenge evaluation state only. It is destructive and has
no confirmation dialog. It is **disabled (403) unless TEARDOWN_TOKEN is configured**.
When enabled, it requires that separate Bearer token. It does not delete demo state.
Do not call during evaluation.

400 malformed/invalid envelope; 401 token missing or wrong; 404 missing participant
or resource; 409 stale/conflicting state; 413 request too large; 415 not JSON;
408 body read timeout; 503 storage unavailable. Error details avoid returning
raw request bodies or SQL. Exceptions not covered by these categories can still
produce the framework's server-error response; this is not an uptime guarantee.

Unversioned aliases `/context`, `/tick`, `/reply`, `/healthz`, `/metadata` are
compatibility conveniences. Submit the base URL and use the specified `/v1` API.

## Website and cross-origin requests (v2)

All five routes also exist at `/demo/v1/...` when `DEMO_ENABLED=true`. They share
the contract and engine, but use a separate DB_PATH + `.demo` database (or explicit
DEMO_DB_PATH). The same optional write API_TOKEN applies. Set CORS_ORIGINS to the
Netlify origin(s); OPTIONS preflight is handled. Required judge paths stay unchanged.
The root `/` is an HTML backend landing page, not the frontend chat app.
