# Vera Studio — Netlify frontend + Render backend

A complete, independent challenge-message playground. **Deploy it yourself; no cloud service is created by this package.**

- **Frontend:** static HTML, CSS and JavaScript modules; no npm installation or build needed. Responsive chat, context editor, API console and connection settings.
- **Backend:** Python / FastAPI / SQLite; all five required `/v1` endpoints, plus an isolated `/demo/v1` namespace for website testing.
- **Engine:** the previous deterministic rule-based composer. No external LLM/API key is needed. This is not a general-purpose AI chat service or actual WhatsApp/Google/booking integration.

## Start here

Read **[INSTRUCTIONS_HINDI.md](INSTRUCTIONS_HINDI.md)** for the complete manual deployment steps, Windows instructions and troubleshooting.

1. Put the extracted repository contents on your Git provider. Create a Render **Python Web Service**, root directory `backend`, build `pip install -r requirements.txt`, start `python start.py`, health check `/v1/healthz`.
2. Edit **one setting**, `API_BASE_URL`, inside `frontend/config.js`:

   ```js
   API_BASE_URL: "https://your-real-render-service.onrender.com",
   ```

   Use your real **base URL** with no `/v1`, `/demo` or `/docs`. Never put a secret here.
3. Drag only the **`frontend` folder** onto Netlify's manual deployment dropzone. Do not upload `backend`, `.env`, databases or the entire repository as a static site. For Git deployment, the root `netlify.toml` sets publish directory `frontend`; leave the build command blank.
4. In Render, set `CORS_ORIGINS` to your actual Netlify origin. Set optional `FRONTEND_URL` to add an interface link to the backend's landing page. Open the Netlify site and start a demo.

**Share the Netlify URL to display the interface. Submit the Render base URL to the challenge's API evaluator.**

## Local run

Terminal 1, from this repository:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python start.py
```

Terminal 2, from the repository root:

```bash
python3 -m http.server 5500 --directory frontend
```

Open `http://localhost:5500`. On localhost, blank `API_BASE_URL` defaults to `http://localhost:8080`. On a public domain, blank config displays the interface with a connection prompt, not fake chatbot replies. Do not double-click `index.html`; JavaScript modules need HTTP serving.

## Features and limits

The playground loads synthetic context, calls the backend, renders returned messages, and sends correctly numbered replies. New sessions use new demo IDs. The context editor retains custom expiry, consent and history, so an invalid/expired scenario may legitimately produce no action. The API console offers demo or real challenge mode; real write requests require a browser confirmation.

Demo and judge state are **different databases**, but this is **not per-visitor/multi-tenant authentication**. Use synthetic data. `API_TOKEN` optionally protects writes; `TEARDOWN_TOKEN` separately enables destructive challenge-state deletion. Secrets are never included in frontend config or browser persistence. A browser override saves only the URL; transcripts and tokens are in memory until refresh. Exported JSON may contain the data you entered.

**Render Free has ephemeral storage and cold starts.** For durable SQLite across redeploys/restarts, choose a paid service and attach a persistent disk, then set `DB_PATH` to `/var/data/vera.sqlite3` on a disk mounted at `/var/data`. The Blueprint defaults to Free for demonstration; it does not silently provision a paid disk. One process / worker / instance is the supported architecture. Changing DB_PATH does not migrate an old database automatically.

## Contents

```text
frontend/                  Static website; upload this folder to Netlify
backend/                   Full FastAPI backend; Render root directory
backend/challenge_reference/ Original supplied challenge documents and fixtures
backend/expanded/          Generated original challenge fixtures (not auto-loaded)
render.yaml                Optional full-repository Render Blueprint
netlify.toml               Netlify publish directory
INSTRUCTIONS_HINDI.md      Detailed deployment and setup guide
scripts/smoke_check.py     Five-endpoint sandbox HTTP check (Python stdlib)
scripts/browser_smoke.py   Optional Playwright UI/regression check
tests/frontend.test.mjs    JavaScript helper, scenario and HTTP-client unit tests
docs/TEST_REPORT.md        What was actually tested and what was not
reports/                   Local test evidence and interface screenshots
```

## Verification

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q
cd ..
node --test tests/frontend.test.mjs
# Start the backend first; demo namespace only:
python3 scripts/smoke_check.py --base-url http://127.0.0.1:8080
```

Node is optional and only used for the frontend test suite; it is not required to deploy/run the website. Browser tests need Playwright plus Chromium, separately installed; see the test report. No cloud deployment, public-HTTPS check or external LLM scoring was performed.

## Sources

Provider setup was checked against official docs on 2026-09-22. These sources inform deployment only; they do not add merchant facts:
- Render FastAPI: https://render.com/docs/deploy-fastapi
- Render free-service limits: https://render.com/docs/free
- Netlify manual/Git deployment: https://docs.netlify.com/deploy/create-deploys/
- FastAPI CORS: https://fastapi.tiangolo.com/tutorial/cors/

The original challenge material and attribution remain in `backend/challenge_reference` and `backend/THIRD_PARTY_NOTICES.md`.
