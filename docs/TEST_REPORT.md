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
