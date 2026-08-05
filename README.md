# WattTipid Backend

WattTipid Backend is a high-performance REST API built using FastAPI to support the WattTipid energy-saving advisory client application.

---

## Technical Stack

- **Web Framework**: FastAPI (Python)
- **Database**: MongoDB (Atlas) via PyMongo
- **Caching & Rate Limiting**: Redis
- **Security**: JWT Authentication (using secure, rotating HttpOnly cookies)
- **Validation**: Pydantic v2

---

## Architecture Overview

The backend conforms to a modular, layered architecture:

```
app/
├── core/             # Base configurations, constants, and cryptographic security helpers
├── database/         # MongoDB Atlas client and Redis cache initialization
├── dependencies/     # Router dependency injection functions (e.g. JWT verification, get_current_user)
├── middleware/       # Custom FastAPI middlewares (CORS setups, security headers)
├── routers/          # API route definitions (Authentication, Energy data, advisory prompts)
├── schemas/          # Pydantic request/response validation schemas
└── main.py           # Application configuration and ASGI entrypoint
```

### Components

1. **Routers (`app/routers/`)**
   - Contain API endpoints.
   - Hand off business logic validation and database operations to PyMongo collections.
   - Example: `auth.py` contains `/register`, `/login`, `/logout`, and `/me`.

2. **Schemas (`app/schemas/`)**
   - Define data contracts using Pydantic.
   - Ensure strict data parsing and validation for input payloads and outbound API representations.

3. **Dependencies (`app/dependencies/`)**
   - Enable reusable dependencies via FastAPI's `Depends` injection framework.
   - Example: extracting and verifying JWT tokens from HttpOnly cookie stores.

4. **Core (`app/core/`)**
   - Controls application environment settings (`config.py`).
   - Houses hashing algorithms and token signatures (`security.py`).

---

## Setup & Useful Commands

Activate Python environment and install packages:

```bash
# Create virtual environment
python -m venv .venv

# Activate environment
.venv/Scripts/activate

# Install dependencies
pip install -r requirements.txt
```

Launch docker compose:

```bash
docker compose up --build
```

Run test suite:

```bash
python -m pytest
```

Run static type checking:

```bash
python -m mypy .\app\main.py
```

# Important Documentation/Links:
```bash
https://reference.langchain.com/python/langchain-core
https://docs.langchain.com/oss/python/langchain/overview
https://docs.langchain.com/oss/python/langchain/streaming
https://medium.com/@pouya_gh/build-your-own-deep-search-part-1-the-core-ai-agent-logic-592eeaf16356
https://lite.duckduckgo.com/lite/
```
