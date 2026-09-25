# WattTipid Backend

WattTipid Backend is an asynchronous REST API built with FastAPI that powers the WattTipid energy-saving advisory web application.

---

## Overview

The backend handles core energy calculations, appliance tracking, user settings, JWT authentication with HTTP-only cookies, registration/email verification via SMTP, Redis caching & rate limiting, asynchronous AI background analysis sessions, and Server-Sent Events (SSE) streaming for an interactive LangChain AI agent (`Gorlock`).

---

## Technology Stack

- **Web Framework**: FastAPI (`0.139.0`) & Uvicorn (`0.51.0`)
- **Database Engine**: MongoDB (Atlas/Local) via PyMongo (`4.13.2`) with typed Pydantic models
- **Caching & Session Storage**: Redis (`6.2.0`)
- **AI & Agent Infrastructure**: LangChain (`1.3.9`), `langchain-google-genai` (`4.3.2`) (Gemini LLM), DuckDuckGo Search (`ddgs` `9.5.3`)
- **Security & Authentication**: JWT (PyJWT/`python-jose`), Google OAuth 2.0 ID Token Verification (`google-auth`), `passlib` with `bcrypt` password hashing, rotating HTTP-only cookies
- **Email Infrastructure**: SMTP (`smtplib` + MIME HTML templates), FastAPI `BackgroundTasks`
- **Validation**: Pydantic v2
- **Testing**: `pytest` (`9.0.3`), `pytest-asyncio`, `httpx`
- **Containerization & Deployment**: Docker (Python 3.12-slim non-root image), Docker Compose, Nginx reverse proxy

---

## Architecture

The backend implements a layered architecture using the Repository Pattern, following a strict **Router → Service → Repository → Database** separation of concerns.
```
watt_tipid_backend/
├── app/
│   ├── constants/         # Domain constants and default configurations
│   ├── core/              # Config settings, logging middleware, security helpers
│   ├── database/          # MongoDB client connection, indexes, PyMongo setup
│   ├── dependencies/      # FastAPI dependency injection (Auth, Services, Repositories)
│   ├── exceptions/        # Custom exception classes and global exception handler
│   ├── middleware/        # Rate limiting middleware, logging context, CORS
│   ├── prompts/           # System prompt templates for AI Advisor & Saving Tips
│   ├── repositories/      # Encapsulated MongoDB data access (Pydantic-typed returns)
│   │   ├── appliance.py
│   │   ├── monthly_energy.py
│   │   ├── refresh_token.py
│   │   ├── saving_tip.py
│   │   ├── saving_tip_session.py
│   │   └── user.py
│   ├── routers/           # HTTP API routes (Auth, Energy, Agents, Tips, Settings)
│   │   ├── agent.py
│   │   ├── appliance.py
│   │   ├── auth.py
│   │   ├── contact.py
│   │   ├── dashboard.py
│   │   ├── saving_tip.py
│   │   └── user_settings.py
│   ├── schemas/           # Pydantic request/response validation contracts
│   ├── services/          # Business logic coordination & AI workflows
│   │   ├── agent_service.py
│   │   ├── appliance_service.py
│   │   ├── auth_service.py
│   │   ├── dashboard_service.py
│   │   ├── email_service.py
│   │   ├── saving_tip_service.py
│   │   ├── tool_executor.py
│   │   └── user_settings_service.py
│   ├── templates/         # HTML & plain-text email body templates
│   ├── tools/             # Request-scoped LangChain agent tools
│   ├── utils/             # Math logic for kWh/tariff cost calculations
│   └── main.py            # FastAPI initialization & ASGI app entrypoint
├── nginx/                 # Nginx reverse proxy configuration
├── tests/                 # Unit & integration test suite (14 test modules)
├── Dockerfile             # Multi-stage non-root container configuration
└── docker-compose.yml     # Local orchestration for API & Redis services
```

### Layer Responsibilities

- **Routers**: Handle HTTP requests/responses, validate Pydantic schemas, delegate execution to services.
- **Services**: Execute application business logic, coordinate workflow state transitions, construct LLM prompts, manage background processing.
- **Repositories**: Direct PyMongo interaction, query execution, document parsing into typed Pydantic models (`UserInDB`, `ApplianceInDB`, `SavingTipInDB`).
- **Database**: MongoDB collection definitions with automated compound indexes and Redis client connection management.

---

## Key Features & Subsystems

### 1. Database & Indexing Strategy
- **MongoDB Collections**: `users`, `refresh_tokens`, `appliances`, `monthly_energy`, `saving_tips`, `saving_tip_sessions`.
- **Indexes**:
  - `users`: Partial unique index on `google_id` (`{"google_id": {"$type": "string"}}`).
  - `refresh_tokens`: TTL index on `expires_at` (`expireAfterSeconds=0`).
  - `appliances`: Compound index on `[("user_id", 1), ("is_active", 1)]`.
  - `monthly_energy`: Compound unique index on `[("user_id", 1), ("month", 1)]`.
  - `saving_tips`: Compound index on `[("user_id", 1), ("status", 1)]`.
  - `saving_tip_sessions`: Compound index on `[("user_id", 1), ("started_at", -1)]`.

### 2. Authentication & Security
- **JWT & Google OAuth 2.0 Integration**: Supports native email/password authentication alongside Google OIDC ID Token verification (`POST /auth/google`) using `google-auth`. Automatically links Google accounts to existing email profiles or registers new users upon verification.
- **Cookie Security**: Emits `access_token` (15-min TTL) and `refresh_token` (7-day TTL) in `HttpOnly`, `SameSite` cookies.
- **Refresh Token Rotation**: Revokes previous token hash (`token_hash`) upon refresh and issues a fresh token pair.
- **Registration Verification**: 6-digit numeric OTP code sent via email, cached in Redis with a 5-minute TTL, rate limited to 3 failed attempts and a 60-second resend cooldown.
- **2-Tier Auth Cache**: `get_current_user` dependency checks Redis (`user:{id}`, 15-min TTL) prior to querying MongoDB.

### 3. Email Infrastructure
- **SMTP Worker**: Built on `smtplib.SMTP` with `STARTTLS`.
- **Async Execution**: Non-blocking dispatch via FastAPI `BackgroundTasks`.
- **Email Workflows**: Registration verification OTP, email change verification, and contact inquiry submissions.

### 4. AI & Agent Architecture (`Gorlock`)
- **LLM Engine**: Powered by LangChain (`langchain-google-genai`) with Google Gemini.
- **User-Scoped Tools**:
  - `get_user_appliances`: Retrieves active household inventory.
  - `get_user_energy_summary`: Computes current total kWh and projected costs.
  - `add_user_appliance` / `update_user_appliance`: Modifies user inventory dynamically.
  - `delete_user_appliance`: Requires explicit user confirmation parameter (`confirmed=True`).
  - `web_search`: Live search via DuckDuckGo (`ddgs`).
- **SSE Event Streaming (`POST /agents/chat/stream`)**: Delivers real-time Server-Sent Events with execution timeline events (`token`, `tool_start`, `tool_end`, `activity`, `complete`, `error`).

### 5. Household Saving Tips State Machine
- **Analysis Lifecycle**: Asynchronous status transition (`IN_PROGRESS` → `COMPLETED` / `FAILED` / `OUTDATED`).
- **Snapshot Versioning**: SHA-256 hash generated from active appliance configurations. If household appliances change mid-analysis, the session is invalidated as `OUTDATED`.
- **24-Hour Cooldown**: Enforces a 24-hour waiting period between full AI household re-evaluations.
- **Calculated vs Reference Tips**:
  - `CALCULATED`: Dynamic PHP savings calculated via `(wattage_watts / 1000) * reduction_hours * 30 * electricity_rate`.
  - `REFERENCE`: Priority assignment based on appliance monthly kWh impact.

---

## API Endpoints

| Method | Path | Description | Authentication |
|---|---|---|---|
| `POST` | `/auth/register` | Initiates registration & sends OTP email | None |
| `POST` | `/auth/register/verify` | Verifies OTP code & creates user account | None |
| `POST` | `/auth/register/resend` | Resends OTP verification code | None |
| `POST` | `/auth/login` | Authenticates user & sets HttpOnly cookies | None |
| `POST` | `/auth/google` | Authenticates via Google OIDC ID token, links account, sets cookies | None |
| `POST` | `/auth/refresh` | Rotates refresh token & updates cookies | Cookie Auth |
| `POST` | `/auth/logout` | Revokes refresh token & clears cookies | Cookie Auth |
| `GET` | `/auth/me` | Fetches authenticated user profile | Cookie Auth |
| `GET` | `/energy/appliances` | Lists all appliances for authenticated user | Cookie Auth |
| `POST` | `/energy/appliances` | Registers a new appliance | Cookie Auth |
| `PUT` | `/energy/appliances/{id}` | Updates existing appliance details | Cookie Auth |
| `DELETE` | `/energy/appliances/{id}` | Deletes an appliance | Cookie Auth |
| `GET` | `/dashboard/summary` | Calculates real-time cost, score, and trends | Cookie Auth |
| `POST` | `/dashboard/monthly-trend` | Logs or updates a historical monthly energy record | Cookie Auth |
| `DELETE` | `/dashboard/monthly-trend/{month}` | Deletes historical monthly energy log | Cookie Auth |
| `GET` | `/user-settings/profile` | Retrieves user settings & electricity rate | Cookie Auth |
| `PUT` | `/user-settings/profile` | Updates basic profile information | Cookie Auth |
| `PUT` | `/user-settings/rate` | Updates custom electricity tariff rate (`₱/kWh`) | Cookie Auth |
| `POST` | `/user-settings/email/request` | Requests email address update & sends OTP | Cookie Auth |
| `POST` | `/user-settings/email/verify` | Verifies OTP and updates email address | Cookie Auth |
| `POST` | `/user-settings/password` | Verifies current password and sets new password | Cookie Auth |
| `POST` | `/agents/chat` | Sync AI agent chat interaction | Cookie Auth |
| `POST` | `/agents/chat/stream` | Async SSE streaming chat with activity timeline | Cookie Auth |
| `GET` | `/saving-tips` | Retrieves saving tips for latest completed session | Cookie Auth |
| `GET` | `/saving-tips/summary` | Aggregates potential monthly/yearly savings | Cookie Auth |
| `PUT` | `/saving-tips/{id}/status` | Updates saving tip lifecycle status | Cookie Auth |
| `GET` | `/saving-tips/analysis-status` | Checks active analysis session and cooldown status | Cookie Auth |
| `POST` | `/saving-tips/generate` | Starts async household AI analysis session | Cookie Auth |
| `POST` | `/contact` | Submits contact inquiry and sends notification email | None |
| `GET` | `/health` | Health check endpoint (verifies Redis connection) | None |

---

## Environment Variables

Configured in `.env` (refer to `.env.example`):

| Category | Variable | Description | Default / Example |
|---|---|---|---|
| **App** | `ENV` | Environment mode (`dev` or `prod`) | `dev` |
| **App** | `PORT` | API execution port | `8080` / `8005` |
| **Database** | `MONGODB_URL` | MongoDB connection URI | `mongodb://localhost:27017` |
| **Database** | `MONGODB_DB_NAME` | Target database name | `watt_tipid_db` |
| **Cache** | `REDIS_URL` | Redis connection URL | `redis://localhost:6379/0` |
| **Security** | `JWT_SECRET` | Secret key for HS256 JWT signing | *(Keep Secret)* |
| **Security** | `GOOGLE_CLIENT_ID` | Google OAuth 2.0 Web Client ID for OIDC verification | `your-client-id.apps.googleusercontent.com` |
| **AI / LLM** | `GEMINI_API_KEY` | API key for Google Gemini LLM | *(Keep Secret)* |
| **Tariff** | `DEFAULT_ELECTRICITY_RATE` | Default rate in PHP per kWh | `12.50` |
| **Email** | `SMTP_HOST` / `SMTP_PORT` | SMTP server configuration | `smtp.gmail.com` / `587` |
| **Email** | `SMTP_USER` / `SMTP_PASSWORD` | SMTP authentication credentials | *(Keep Secret)* |
| **Email** | `EMAILS_FROM_EMAIL` | Sender email address | `no-reply@watttipid.com` |

---

## Development Setup

### Local Run with Virtual Environment

1. Navigate to the backend directory:
   ```bash
   cd watt_tipid_backend
   ```

2. Create and activate a Python 3.12 virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up `.env` from `.env.example` and update database credentials.

5. Launch the FastAPI Uvicorn development server:
   ```bash
   uvicorn app.main:app --reload --port 8005
   ```

### Docker Compose Run

Run API and Redis instances in isolated Docker containers:

```bash
docker compose up --build
```

---

## Testing & Verification

Run the test suite with `pytest`:

```bash
python -m pytest
```

Run static type checking with `mypy`:

```bash
python -m mypy app/main.py
```

## License

Copyright (c) 2026 Paul Corsino. All rights reserved.

This repository is publicly available for portfolio and educational viewing purposes only. No permission is granted to copy, modify, distribute, or use the source code for commercial purposes without prior written permission.
