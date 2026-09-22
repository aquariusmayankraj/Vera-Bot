<<<<<<< HEAD
# Test report

## Executed verification

The package was exercised locally on Python 3.13.5. Installed dependency versions
are captured in `reports/environment.json`. Source/configuration changes were
followed by another complete regression run.

| Check | Observed result | Evidence |
|---|---|---|
| Automated regression suite | 97 passed; 0 failed | `reports/pytest.txt`, `reports/pytest.xml` |
| Fresh ZIP extraction and regression run | 97 passed from the extracted package | `reports/zip_roundtrip_tests.txt` |
| Actual local HTTP integration | 18 checks passed | `reports/http_smoke_test.json` |
| Generated canonical pair audit | 30 inspected; 20 composed; 10 explicitly suppressed | `reports/canonical_audit.json`, `submission.jsonl` |
| Supplied-simulator wrapper warmup | Loaded 5 categories, 10 seed merchants, 15 seed customers | `reports/official_wrapper_warmup.txt` |
| Original challenge file integrity | All 16 supplied files byte-identical | `reports/source_integrity.json` |
| Python syntax compilation | Application, scripts, deployment launcher and tests compiled | Local compileall execution |
| Deployment configuration parsing | Render and Compose YAML parsed; JSON examples parsed | Local structural check only |

The 18 HTTP checks use a real Uvicorn process and stdlib HTTP client, not just
FastAPI's in-process TestClient. They cover all five required endpoints, context
idempotency/conflicts, first-message templates, grounded output, duplicate ticks,
acceptance draft, reply retry and opt-out. The warmup wrapper check used the
Ollama provider object without contacting an Ollama server or making LLM calls;
it verifies HTTP warmup and optional Bearer transport, **not scoring**.

Regression cases include multiple concurrent context/tick requests, durable state
across app restarts, context injection, current-fact re-resolution, recipient
ownership, purpose-scoped consent, opt-out history, session-window boundaries,
expired/future triggers, no fabricated offers/slots, replay conflicts, request
limits and conversation intent handling. Passing these tests is not a proof of
all possible hidden judge cases or adversarial inputs.

## Why some canonical previews are suppressed

The supplied expanded combinations sometimes lack customer consent, competitor
identity, festival date/name, milestone figures or a matching metric movement.
The audit records the specific reason and test ID. The composer returns a marked
suppression rather than inventing facts; the HTTP scheduler omits unsafe sends.
Thus “30 audited” does not mean “30 messages sent” or “30 official passes”. Live
HTTP scheduling can additionally suppress expiry, due-date, repeat and cadence
cases when a particular simulated clock/history makes them ineligible.

## Not verified / important limits

- No public cloud deployment, public HTTPS reachability, provider uptime or DNS
  setup was performed. Manual deployment belongs to the user.
- Docker is not available in this execution environment, so no Docker image build
  or container-host smoke test was performed. YAML parsing is not a deploy test.
- A fresh isolated virtual-environment dependency installation was attempted but
  blocked by this environment's DNS/network restriction when reaching PyPI. See
  `reports/clean_install_attempt.txt`. The actual regression and HTTP results use
  the available installed dependencies listed in `reports/environment.json`.
  Fresh-install portability must be checked on a network-enabled deployment host.
- No external LLM scorer call, official hidden evaluation, leaderboard result or
  guaranteed engagement/quality score is included.
- No load benchmark at the public host, multi-replica test, real WhatsApp delivery,
  real Meta template approval, booking integration or Google profile write occurred.
- No claim of production multi-tenant security, comprehensive language support or
  independent verification of synthetic research/regulatory source assertions.

## Reproduce

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
# Start `python start.py` in a separate terminal first:
python scripts/smoke_test.py --base-url http://127.0.0.1:8080
python scripts/export_submission.py
```

Only run demos on a disposable test state or before evaluation. Do not reset an
active evaluation or mix unrelated simulation clocks in the same stored state.
=======
# Version 2 verification report

Executed locally on 2026-09-22. This report describes the delivered source, not a deployed Netlify/Render service.

| Check | Observed result | Evidence |
|---|---|---|
| Backend regression suite | **117 passed**, 0 failed | `reports/backend-tests.txt`, `reports/backend-junit.xml` |
| Frontend JavaScript unit tests | **45 passed**, 0 failed | `reports/frontend-tests.txt` |
| Standalone real HTTP sandbox checks | **20 passed** | `reports/http-tests.txt`, `reports/http-sandbox.json` |
| Headless browser UI harness | Chat/STOP, console, invalid JSON, settings, retry and mobile layout checks passed; 0 page errors | `reports/browser-tests.txt`, `scripts/browser_smoke.py` |
| Browser-to-local-backend scenario matrix | All **20 combinations** (5 categories × 4 triggers) returned messages | `reports/browser-tests.txt` |
| Original canonical fixture audit | 30 previews: 20 composed, 10 explicitly suppressed | `backend/submission.jsonl`, `backend/reports/canonical_audit.json` |
| JS syntax / configuration structure | All four JS source modules checked; Render/Compose YAML and Netlify TOML parsed | Reproducible commands below |
| Fresh ZIP extraction | Backend and JS suites repeated from the extracted archive | `reports/zip-roundtrip.txt` |

The backend suite includes the previous 97 regression cases, plus 20 website integration cases covering both endpoint namespaces, state isolation, explicit and wildcard CORS, preflight, validation/auth error headers, HTML escaping, demo disabling, optional auth, separate persistence, teardown protection, environment parsing and same-file rejection.

The 20 standalone HTTP checks run through a real local Uvicorn server. They cover health/metadata, CORS preflight, three context pushes/replays/stale-version errors, grounded tick output, repeated-tick suppression, reply, exact-turn retry, STOP and unchanged judge context counts after demo writes. The browser simulated a response lost **after the server processed it** and verified that Retry sends the identical JSON request and does not duplicate the user message.

## Browser execution limitation

The installed Chromium has an administrator policy blocking all URL navigation, including localhost. That policy was **not changed**. The UI harness was therefore run with `--inline-local-render`: it rendered the local HTML/CSS in `about:blank`, combined the same JavaScript source modules for script injection, and made real HTTP fetch calls to the local backend. This validates interaction/rendering and engine integration, but **does not validate browser navigation, native ES-module network loading from a deployed host, Netlify `_headers` delivery/CSP enforcement, or a public HTTPS deployment**. Module syntax/helpers were independently tested by Node, and CORS origins/preflight were exercised by API and HTTP tests. No browser page errors were observed in this harness. Source screenshots are `reports/desktop-chat.png`, `reports/desktop-empty.png` and `reports/mobile-chat.png`.

## Environment

Python 3.13.5; Node v22.16.0; installed FastAPI/Uvicorn/Pydantic versions match `backend/requirements.txt`. Exact versions are in `reports/environment.json`. Runtime dependencies were used from the supplied environment; a fresh internet dependency install was **not** completed in this version's testing. Render must download these requirements during its build.

## What was not tested or promised

No Netlify or Render resource was created. No DNS, custom domain, public HTTPS, provider uptime, paid disk attachment or live cloud deployment was tested. A ZIP/YAML file is configuration, not a deployment. No Docker image build, hosted load benchmark, multi-tenant security audit, native mobile-app build or external LLM judge run occurred. No real WhatsApp message, Meta template approval, Google profile update, booking or payment was performed. Test passes are not a guarantee of unseen judge quality or all possible inputs.

The fixture audit's 10 suppressed rows are not 10 successful messages: the supplied combinations lack needed facts/consent or contain inconsistent context. The code does not silently repair that fixture data. See the audit JSON for per-case reasons. These original historical fixture previews differ from the frontend's current-time synthetic demo scenarios.

## Reproduce

From the repository root:

```bash
cd backend
python -m pip install -r requirements-dev.txt
python -m pytest -q
cd ..
node --test tests/frontend.test.mjs
# Start backend in another terminal first:
python3 scripts/smoke_check.py --base-url http://127.0.0.1:8080 --origin http://localhost:5500
```

Optional browser checks (not runtime dependencies):

```bash
python3 -m pip install playwright
python3 -m playwright install chromium
# Also start the frontend: python3 -m http.server 5500 --directory frontend
python3 scripts/browser_smoke.py --backend-base-url http://127.0.0.1:8080
# Only for environments where local-source rendering is needed:
python3 scripts/browser_smoke.py --backend-base-url http://127.0.0.1:8080 --inline-local-render
```

`--chromium /path/to/chromium` selects a browser executable; without it the script uses system Chromium when available or Playwright's installed default. Browser tests change only demo state. The inherited `backend/scripts/smoke_test.py` is a separate original test that writes judge state, so do not run it during evaluation.

For syntax only: `node --check frontend/src/app.js` (repeat for api.js, demo.js, utils.js).
>>>>>>> b7310dbb2c6a1968b791bd65350edc8bbb40aaf7
