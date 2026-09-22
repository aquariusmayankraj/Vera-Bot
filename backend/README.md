# Vera FastAPI backend

This folder is independently deployable as a Render Python Web Service. In the full repository choose Root Directory `backend`; if only this folder's contents are in the repository, leave Root Directory blank.

- Build: `pip install -r requirements.txt`
- Start: `python start.py`
- Health: `/v1/healthz`
- Runtime: Python 3.13.5, one worker/instance.
- Public root `/` now displays an HTML landing page. `FRONTEND_URL` optionally links to the Netlify frontend.

Create a local virtual environment, install requirements, copy `.env.example` to `.env`, edit your team/contact details, and run `python start.py`. The complete local/Render/Netlify steps are in `../INSTRUCTIONS_HINDI.md`.

## API compatibility

All required `/v1/context`, `/v1/tick`, `/v1/reply`, `/v1/healthz`, `/v1/metadata` endpoints are retained. The website uses additional `/demo/v1/...` paths, backed by a separate SQLite database. `DEMO_ENABLED=true` is needed for the website. These changes do not replace the deterministic engine with an LLM.

`CORS_ORIGINS=*` is the public synthetic-demo default. Restrict to your real frontend origin after deployment. Optional `API_TOKEN` protects POSTs; health/metadata are public. `TEARDOWN_TOKEN` separately enables destructive challenge-state reset, which is disabled by default. No real merchant outreach is performed.

`DB_PATH=data/vera.sqlite3` is ephemeral on Render Free. For retained state attach an actual persistent disk on a paid web service and set DB_PATH on it. See the full instructions; never scale independent SQLite replicas.

## Tests and source artifacts

```bash
pip install -r requirements-dev.txt
python -m pytest -q
python scripts/export_submission.py
```

`challenge_reference/` preserves the original user-supplied challenge pack. `expanded/` and `submission.jsonl` are original-dataset offline previews, not automatic runtime seed data and not guaranteed judge passes. The existing `scripts/smoke_test.py` targets the real `/v1` state with a historical simulation clock; use `../scripts/smoke_check.py` for the website sandbox and do not run judge-state demos during evaluation.

See `docs/API_CONTRACT.md` for envelopes and `../docs/TEST_REPORT.md` for current test results/limitations. The optional scorer wrapper is not part of normal runtime and no external scorer was executed.
