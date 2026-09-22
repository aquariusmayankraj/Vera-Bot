# Deployment security and data boundaries

This application is a synthetic-data challenge/demo, not a production multi-tenant service.

## Authentication and origin checks

Default API writes are public to match the submitted-endpoint workflow. Set `API_TOKEN` on Render to require Bearer authentication for both `/v1` and `/demo/v1` writes. Health and metadata stay public. The evaluator must support this header before enabling a token during evaluation. Enter the token only in the website Settings password field. The field is cleared when editing the backend address, and no token is persisted to browser storage or sent on GET probes. Reloading forgets it. API response/body logs deliberately exclude request headers.

CORS is not authentication: it controls browser response access, not requests from arbitrary HTTP clients. `CORS_ORIGINS=*` is a convenient synthetic-demo default with no cookie credentials. Set exact deployed origins for normal use. Custom domains/preview URLs must be accounted for. `_headers` provides a frontend CSP and other static-site headers. HTTPS-to-HTTP and URLs containing credentials, paths, query parameters or fragments are rejected by the UI.

There is no per-user login, API quota, WAF, rate limiter or continuous security monitoring in this ZIP. Do not put real merchant/customer/patient data on the public demo. Horizontal scaling or a public SaaS requires an authentication/authorization, durable database and abuse-control redesign.

## State isolation and retention

Judge requests use `DB_PATH`; ordinary website requests use `DEMO_DB_PATH` or the adjacent `.demo` file. They share an engine, not data. Demo users are not individually isolated from other demo users. Random session IDs prevent accidental reuse, not a true tenancy boundary. The API console can deliberately target judge state after confirmation; keep it out of active evaluations.

The application logs no request bodies by default. The browser keeps transcripts/last 80 request records in page memory, not localStorage. Only the explicit backend-URL override uses localStorage. Exported JSON can contain all manually supplied context/messages and should be treated as sensitive. Do not enter secrets in chat/JSON.

`POST /v1/teardown` is disabled until the separate `TEARDOWN_TOKEN` is configured. Correct auth wipes challenge state only; no UI reset calls it. Old synthetic demo data is not deleted by New session. Lazy inactivity expiry applies per store according to `STATE_TTL_HOURS` (default 24): after inactivity it can clear the entire store on a subsequent write. This does not guarantee row-by-row timed deletion or remove host snapshots/backups. Backups, access controls and lifecycle deletion are the deployer's responsibility.

Render filesystem durability depends on an actually attached persistent disk and a DB_PATH on that disk, not just changing a string. Free-instance state loss is documented in the deployment guide.

## External actions

The runtime makes no outbound LLM/WhatsApp/Google/booking calls. It returns simulated template-shaped drafts/actions. No template is represented as Meta approved and no proposed account change is claimed as executed. The optional original LLM judge wrapper is separate and can send synthetic test context to a provider only when you configure and run it.
