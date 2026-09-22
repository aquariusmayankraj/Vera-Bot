# Deployment reference

The full ordered guide, exact environment settings, Windows commands and troubleshooting are in [INSTRUCTIONS_HINDI.md](../INSTRUCTIONS_HINDI.md). The quick start is in [README.md](../README.md).

## Defaults

| Component | Deployment artifact | Configuration |
|---|---|---|
| Render Python service | whole repository, root `backend` | root `render.yaml`, `backend/.env.example` |
| Netlify static site | `frontend/` contents | `frontend/config.js`, `frontend/_headers` |
| Netlify Git publish | repository root | `netlify.toml`: publish `frontend`, no build |
| Backend-only Git repo | contents of `backend/` | no rootDir; `backend/render.yaml` becomes repo `render.yaml` |
| Optional Docker | `backend/Dockerfile` | local `backend/docker-compose.yml`; not tested here |

All frontend backend-address configuration is centralized in `frontend/config.js`. Settings can override it for one browser. No Netlify server function/proxy or extra API port configuration is needed. The backend root landing page can link to the Netlify site via `FRONTEND_URL`; this does not redirect API routes or configure CORS.

The default Render Blueprint uses a **Free** instance and **no persistent disk**. Importing a Blueprint is optional; do not also create a duplicate manual service. Paid compute plus a persistent disk mounted at `/var/data` and `DB_PATH=/var/data/vera.sqlite3` is the documented durable-SQLite setup. Do not enable multiple workers or replicas with independent SQLite files. Backups/migration are not automated by the package.

## Official provider sources (checked 2026-09-22)

- Render Python/FastAPI commands: https://render.com/docs/deploy-fastapi
- Render service Blueprint fields: https://render.com/docs/blueprint-spec
- Render free idle/filesystem limits: https://render.com/docs/free
- Render durable disk: https://render.com/docs/disks
- Netlify static/manual/Git deployment: https://docs.netlify.com/deploy/create-deploys/
- Netlify headers file: https://docs.netlify.com/manage/routing/headers/
- FastAPI CORS configuration: https://fastapi.tiangolo.com/tutorial/cors/

Provider dashboards/limits can change; this is not a price quote or a public deployment certificate.
