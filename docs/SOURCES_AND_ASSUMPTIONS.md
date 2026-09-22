# Sources, assumptions and known source differences

## User-provided sources

The uploaded `magicpin-ai-challenge` archive is copied into `challenge_reference/`
without edits. It contains the challenge brief, testing brief, engagement notes,
seed dataset, generator, API examples, case studies and original judge simulator.
The user's supplied website copy specifies the public URL and five `/v1`
endpoints. The older general brief also describes offline Python/JSONL submission;
this implementation delivers those artifacts **in addition to** the HTTP API.

The HTTP `challenge-testing-brief.md` is treated as the operational envelope
contract. Its `tick.now` and `reply.received_at` define simulation time. The general
brief remains the basis for context types and message constraints. No unseen
source details are filled with assumed merchant facts.

The synthetic data is not real merchant/patient data. Research and regulation
headlines in the fixture are quoted/attributed as supplied context, not certified
medical/legal facts. Do not use this challenge dataset to advise real patients,
operate a pharmacy, or run actual merchant outreach.

## Explicit implementation choices where sources are incomplete or inconsistent

- Context keys include scope as well as ID, avoiding collisions across categories,
  merchants, customers and triggers. Repeated same version is a no-op.
- The body-length rule has no hard message cap. The HTTP request cap is implemented
  as 500 * 1024 bytes (500 KiB), a stated interpretation of the source's “500 KB”.
- Conflicting weekday labels are not trusted over an explicit ISO slot timestamp.
  The code computes weekday/time from the ISO value and supplied/local timezone.
  Missing dates, prices or slot availability are not invented.
- Some generated canonical pairs combine placeholder triggers and mismatched
  merchant/customer context, including absent purpose-specific consent. The audit
  preserves these inputs and reports suppression; it does not repair their data.
- General action messages have one primary CTA. STOP handling is always recognized.
  Draft delivery can legitimately have `cta: none`.
- Our cadence, fail-closed consent mapping, scoped dedup, deterministic tie-breaks
  and fallback language policy are implementation choices, not claims that the
  source mandates the exact same algorithms.

## Original simulator caveats and wrapper differences

The supplied simulator's BotClient uses the real current clock. Several fixture
triggers expire in April/May 2026; replaying them in September 2026 should not force
an expired send. `scripts/run_official_judge.py` imports the original file, chooses
an explicit simulation start (`--now`), advances ticks/replies, and warms up all
seed merchant/customer records (the original warmup loads only five merchants and
no customers). Optional Bearer transport is supported by the wrapper. Provider/key/
model come from environment variables instead of editing the original file.

The original scoring implementation is not modified. The original `all` scenario
is not the same as `full_evaluation`; the latter scores seed-trigger batches rather
than the generated 30 canonical test pairs. Therefore the exported 30-pair preview
and optional LLM-scoring run are distinct checks. Invalid/unsafe fixture scenarios
can still produce no action. No optional external LLM scoring was performed in
this delivery and no leaderboard result is claimed.

## External primary documentation consulted

These links support deployment mechanics/dependency usage only; they are not
additional merchant/business facts. Consult the live pages again before paying
for a hosting plan because product configuration and pricing can change.

- FastAPI manual deployment / Uvicorn: https://fastapi.tiangolo.com/deployment/manually/
- FastAPI deployment concepts: https://fastapi.tiangolo.com/deployment/concepts/
- Render FastAPI guide: https://render.com/docs/deploy-fastapi
- Render Blueprint schema: https://render.com/docs/blueprint-spec
- Render durable disk behavior: https://render.com/docs/disks
- Render health probes: https://render.com/docs/health-checks
- FastAPI package metadata: https://pypi.org/project/fastapi/0.128.2/
- Uvicorn pinned release: https://pypi.org/project/uvicorn/0.48.0/
- Pydantic pinned release: https://pypi.org/project/pydantic/2.13.4/

The included Render Blueprint follows the consulted schema with Docker runtime,
manual deploys, one instance and an attached disk. It is a **paid** resource
configuration; it is not an assertion of free service or a price quote. Actual
cloud deployment and Docker image build were not executed here.
