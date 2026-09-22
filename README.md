Vera Challenge Bot

A deterministic, context-grounded challenge message engine exposed
through a REST API.

OpenAPI: 3.1
Version: 1.0.0
Server: Uvicorn / FastAPI
Note: This service does not perform real WhatsApp delivery or real
account changes.

Overview

Vera Challenge Bot provides a small API for managing challenge-related
context and generating deterministic replies.

The API is organized into two groups:

Judge API --- health, metadata, context, ticking the engine, and
generating replies.

Lifecycle --- teardown/reset of the current runtime state.

API Endpoints

Method                  Endpoint                Purpose

GET                     /v1/healthz           Check whether the
service is healthy

GET                     /v1/metadata          Get service metadata

POST                    /v1/context           Provide/update context
for the engine

POST                    /v1/tick              Advance the engine
using the supplied tick
information

POST                    /v1/reply             Generate a reply for a
conversation message

Request Models

ReplyRequest

The reply endpoint accepts:

conversation_id --- required string, 1--240 characters

merchant_id --- optional string

customer_id --- optional string

from_role --- required string

message --- required string, 1--12,000 characters

received_at --- required date-time

turn_number --- required integer, 1--10,000

Example:

{
  "conversation_id": "conv-001",
  "merchant_id": "merchant-001",
  "customer_id": "customer-001",
  "from_role": "customer",
  "message": "I need help with my order.",
  "received_at": "2026-09-22T10:00:00Z",
  "turn_number": 1
}

TickRequest

The tick endpoint accepts:

now --- required date-time

available_triggers --- list of available trigger strings

Example:

{
  "now": "2026-09-22T10:00:00Z",
  "available_triggers": []
}

Teardown Response

A successful teardown returns a response similar to:

{
  "accepted": true,
  "cleared": true
}

This indicates that the teardown request was accepted and the runtime
state was cleared.

Health Check

The health endpoint returns the service status and runtime/context
information.

Example response:

{
  "status": "ok",
  "uptime_seconds": 779,
  "contexts_loaded": {
    "category": 0,
    "merchant": 0,
    "customer": 0,
    "trigger": 0
  }
}

The exact uptime_seconds value changes while the service is running.

Validation

The API uses request validation. Invalid or missing fields can result
in:

422 Validation Error

Validation errors contain details about the field that failed
validation.

For example, ReplyRequest requires fields such as conversation_id,
from_role, message, received_at, and turn_number.

Interactive API Documentation

When the application is running locally, FastAPI provides interactive
API documentation.

Open:

http://127.0.0.1:8080/docs

The Swagger UI can be used to inspect the endpoints, request schemas,
response schemas, and execute API requests directly from the browser.

Running Locally

Create and activate a virtual environment:

Windows

python -m venv .venv
.venv\Scripts\activate

Install dependencies:

pip install -r requirements.txt

Start the API:

python start.py

If the project is configured to run through Uvicorn directly, the
equivalent command is:

uvicorn vera.api:app --host 0.0.0.0 --port 8080

Then open:

http://127.0.0.1:8080/docs

Example API Flow

A typical flow is:

1. Start the API
       ↓
2. Check /v1/healthz
       ↓
3. Load/provide context using /v1/context
       ↓
4. Advance state using /v1/tick
       ↓
5. Send a conversation message using /v1/reply
       ↓
6. Receive the generated response
       ↓
7. Use /v1/teardown to clear runtime state

Technology

The API is built around:

Python

FastAPI

Uvicorn

Pydantic

OpenAPI 3.1

Important Note

Vera Challenge Bot is designed as a deterministic challenge/message
engine. It should not be interpreted as a real WhatsApp integration, and
the documented service does not perform real WhatsApp delivery or
account changes.
