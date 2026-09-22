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
