<<<<<<< HEAD
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

=======
# Vera Challenge Bot

A deterministic, context-grounded challenge message engine exposed through a REST API.

**Version:** 1.0.0  
**OpenAPI:** 3.1  
**Framework:** FastAPI  
**Server:** Uvicorn

> **Note:** This service does not perform real WhatsApp delivery or real account changes.

---

## Overview

Vera Challenge Bot is a deterministic API-based challenge/message engine.

It provides endpoints for:

- Checking service health
- Getting service metadata
- Loading and managing context
- Advancing the engine using ticks
- Generating conversation replies
- Clearing runtime state

The API is designed to provide predictable, context-grounded responses.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v1/healthz` | Check API health |
| `GET` | `/v1/metadata` | Get API metadata |
| `POST` | `/v1/context` | Provide/update context |
| `POST` | `/v1/tick` | Advance the engine |
| `POST` | `/v1/reply` | Generate a reply |
| `POST` | `/v1/teardown` | Clear/reset runtime state |

---

## API Documentation

Once the server is running:

### Swagger UI

```text
http://127.0.0.1:8080/docs
```

### OpenAPI Specification

```text
http://127.0.0.1:8080/openapi.json
```

Swagger UI can be used to view schemas and test the API directly.

---

## API Flow

```text
             Start Server
                  |
                  v
          GET /v1/healthz
                  |
                  v
         GET /v1/metadata
                  |
                  v
         POST /v1/context
                  |
                  v
           POST /v1/tick
                  |
                  v
          POST /v1/reply
                  |
                  v
        Receive Response
                  |
                  v
        POST /v1/teardown
                  |
                  v
        Runtime State Cleared
```

---

## 1. Health Check

### Request

```http
GET /v1/healthz
```

### Example Response

```json
>>>>>>> 89373e8 (Update README documentation)
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
<<<<<<< HEAD

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

=======
```

---

## 2. Metadata

### Request

```http
GET /v1/metadata
```

Returns metadata about the Vera Challenge Bot API.

---

## 3. Context

### Request

```http
POST /v1/context
```

This endpoint provides or updates context used by the challenge/message engine.

The exact request structure is defined by the `ContextRequest` schema in Swagger.

---

## 4. Tick

### Request

```http
POST /v1/tick
```

The tick endpoint advances the engine using the supplied time and available triggers.

### TickRequest

| Field | Type | Required |
|------|------|----------|
| `now` | `date-time` | Yes |
| `available_triggers` | `array[string]` | Yes |

### Example

```json
{
  "now": "2026-09-22T10:00:00Z",
  "available_triggers": []
}
```

---

## 5. Reply

### Request

```http
POST /v1/reply
```

The reply endpoint generates a response for a conversation message.

### ReplyRequest

| Field | Type | Required | Limits |
|------|------|----------|--------|
| `conversation_id` | string | Yes | 1–240 characters |
| `merchant_id` | string/null | No | - |
| `customer_id` | string/null | No | - |
| `from_role` | string | Yes | - |
| `message` | string | Yes | 1–12,000 characters |
| `received_at` | date-time | Yes | - |
| `turn_number` | integer | Yes | 1–10,000 |

### Example Request

```json
{
  "conversation_id": "conv-001",
  "merchant_id": "merchant-001",
  "customer_id": "customer-001",
  "from_role": "customer",
  "message": "I need help with my order.",
  "received_at": "2026-09-22T10:00:00Z",
  "turn_number": 1
}
```

---

## 6. Teardown

### Request

```http
POST /v1/teardown
```

Clears the current runtime state.

### Example Response

```json
{
  "accepted": true,
  "cleared": true
}
```

---

## Validation

The API uses Pydantic/FastAPI request validation.

Invalid requests return:

```text
422 Validation Error
```

Example:

```json
{
  "detail": [
    {
      "loc": [
        "body",
        "message"
      ],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

---

## Project Structure

```text
vera-bot/
│
├── bot.py
├── start.py
│
├── requirements.txt
├── requirements-dev.txt
│
├── Dockerfile
├── Procfile
├── render.yaml
├── docker-compose.yml
│
├── .env.example
├── .gitignore
│
├── MANIFEST.sha256
├── submission.jsonl
├── templates.json
├── THIRD_PARTY_NOTICES.md
│
├── docs/
│   └── TEST_REPORT.md
│
└── vera/
    ├── __init__.py
    ├── api.py
    ├── composer.py
    ├── config.py
    ├── policy.py
    ├── replies.py
    ├── schemas.py
    ├── service.py
    ├── store.py
    ├── templates.py
    └── utils.py
```

---

## Core Components

### `vera/api.py`

Contains the FastAPI application and API routes.

### `vera/schemas.py`

Contains request and validation schemas such as:

- `ContextRequest`
- `ReplyRequest`
- `TickRequest`

### `vera/service.py`

Contains the main service/application logic.

### `vera/store.py`

Handles runtime/context state.

### `vera/replies.py`

Contains reply-related logic.

### `vera/composer.py`

Handles message/content composition.

### `vera/policy.py`

Contains policy/rule-related logic.

### `vera/templates.py`

Contains message/template functionality.

### `vera/config.py`

Contains application configuration.

### `vera/utils.py`

Contains shared utility functions.

---

## Local Setup

### Prerequisites

- Python 3.x
- Git
- pip

### Clone Repository

```bash
git clone https://github.com/aquariusmayankraj/Vera-Bot.git
cd Vera-Bot
```

### Create Virtual Environment

Windows:

```bash
python -m venv .venv
```

Activate:

```bash
.venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Run the Application

Start the application:

```bash
>>>>>>> 89373e8 (Update README documentation)
python start.py

<<<<<<< HEAD
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
=======
Alternatively:

```bash
uvicorn vera.api:app --host 0.0.0.0 --port 8080
```

Then open:

```text
http://127.0.0.1:8080/docs
```

---

## Quick Start

```bash
git clone https://github.com/aquariusmayankraj/Vera-Bot.git

cd Vera-Bot

python -m venv .venv

.venv\Scripts\activate

pip install -r requirements.txt

python start.py
```

Open:

```text
http://127.0.0.1:8080/docs
```

---

## Testing

The easiest way to test the API is through Swagger UI.

1. Start the server.
2. Open `/docs`.
3. Select an endpoint.
4. Click **Try it out**.
5. Enter the request body.
6. Click **Execute**.
7. Check the response status and response body.

Example successful teardown:

```json
{
  "accepted": true,
  "cleared": true
}
```

---

## Docker

Build the image:

```bash
docker build -t vera-bot .
```

Run the container:

```bash
docker run -p 8080:8080 vera-bot
```

Open:

```text
http://127.0.0.1:8080/docs
```

### Docker Compose

```bash
docker compose up --build
```

Stop:

```bash
docker compose down
```

---

## Environment Variables

An example environment file is provided:

```text
.env.example
```

On Windows:

```bash
copy .env.example .env
```

Update `.env` with the required environment values.

> Do not commit secrets or private credentials to GitHub.

---

## Deployment

The repository includes:

```text
render.yaml
```

for Render-based deployment.

After pushing changes to GitHub, the connected Render service can deploy the latest commit when automatic deployment is enabled.

After deployment, open:

```text
https://your-service-url/docs
```

and verify:

```text
GET /v1/healthz
```

A successful deployment should return a response containing:

```json
{
  "status": "ok"
}
```

---

## HTTP Status Codes

| Status | Meaning |
|--------|---------|
| `200` | Successful request |
| `422` | Request validation error |
| `500` | Internal server error |

---

## OpenAPI

The API follows OpenAPI 3.1.

Swagger UI:

```text
/docs
```

OpenAPI JSON:

```text
/openapi.json
```

---

## Important Notes

Vera Challenge Bot is a deterministic challenge/message engine.

It does **not** perform:

- Real WhatsApp message delivery
- Real WhatsApp account modifications
- Real account changes
- External WhatsApp actions

The service is intended for challenge evaluation, testing, and deterministic message processing.

---

## Technology Stack

```text
Python
  |
  +-- FastAPI
  |
  +-- Uvicorn
  |
  +-- Pydantic
  |
  +-- OpenAPI 3.1
  |
  +-- Docker
  |
  +-- Render
```

---

## Project Status

```text
Vera Challenge Bot
Version: 1.0.0
OpenAPI: 3.1
Framework: FastAPI
Server: Uvicorn
```

---

## License

This project is provided for challenge/evaluation purposes.
>>>>>>> 89373e8 (Update README documentation)
