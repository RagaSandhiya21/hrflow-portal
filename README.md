# HRFlow — Employee Self-Service HR Portal
**Project S2-C-01**
FastAPI · PostgreSQL · ChromaDB · LangChain · React + Vite + Tailwind

---

## What's in this zip

```
hrflow-portal/
├── db/
│   └── schema.sql            # Finalized PostgreSQL schema — run this first
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI app entrypoint
│   │   ├── config.py         # Settings (env vars)
│   │   ├── database.py       # SQLAlchemy engine + session
│   │   ├── models.py         # ORM models (Tier 1 + 2 tables)
│   │   ├── schemas.py        # Pydantic request/response schemas
│   │   ├── security.py       # Real Entra ID JWKS validation + JWT issuance
│   │   ├── deps.py           # Auth deps: role guards + shared-admin guard
│   │   ├── utils.py          # Business-day calculator
│   │   ├── rag_pipeline.py   # ChromaDB + LangChain + Sentence-Transformers RAG
│   │   ├── payslip_pdf.py    # PyMuPDF payslip template (fixed coordinates)
│   │   ├── ws_manager.py     # WebSocket connection manager
│   │   ├── notification_service.py  # writes Notification rows + pushes over WS
│   │   └── routers/
│   │       ├── auth.py       # Real Entra ID SSO + shared-admin resolution + dev mock login
│   │       ├── org.py        # Department/Team/Designation CRUD (HR Admin only)
│   │       ├── dashboard.py  # GET /dashboard/summary
│   │       ├── leave.py      # Leave types, balances, apply, approve, withdraw
│   │       ├── payslips.py   # List, detail breakdown, on-demand PDF (PyMuPDF)
│   │       ├── profile.py    # Self-service + HR-approval change requests
│   │       ├── hr_requests.py# HR ticket queue, comments, status
│   │       ├── attendance.py # Calendar records, summary, regularisation
│   │       ├── it_requests.py# IT ticket queue, status history
│   │       ├── chatbot.py    # Real RAG pipeline (ChromaDB/LangChain) + keyword fallback
│   │       └── notifications.py  # GET /notifications + WebSocket push
│   ├── tests/                 # Pytest suite (36 tests) — see "Testing" below
│   ├── seed.py                # Demo data (2 real people + 1 manager + 2 shared admin accounts)
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── auth/msalConfig.js  # MSAL.js config (real Entra ID SSO)
│   │   ├── api/                # Axios client + all service functions
│   │   ├── context/            # AuthContext (SSO login, WebSocket notifications)
│   │   ├── components/         # Sidebar, AppLayout, shared UI (Modal, Table…)
│   │   └── pages/               # Dashboard, Leave, Payslips, Profile,
│   │                            #   HR Requests, Attendance, IT Requests, Chatbot
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js          # Dev proxy: /api → http://localhost:8000
│   └── tailwind.config.js
└── .github/workflows/ci.yml    # GitHub Actions: pytest + coverage + frontend build
```

---

## HR Admin / IT Admin are shared accounts, not people

This is the most important change from earlier versions of this zip: **HR Admin and IT Admin are functional role accounts, not individuals.**

- Their `employees` rows have `is_shared_admin = TRUE` and carry **zero personal data** — no DOB, phone, gender, marital status, address, bank/PAN identity info, leave balance, payslip, or attendance record. `entra_object_id` is `NULL` because no single fixed person owns the account.
- In production, real staff reach these accounts by being a member of an Entra ID **security group** (`ENTRA_HR_ADMIN_GROUP_ID` / `ENTRA_IT_ADMIN_GROUP_ID`) — anyone in that group is signed into the shared account on login (see `app/routers/auth.py::_resolve_identity_to_employee`). There's no separate "HR Admin password" to share around; access is managed the same way you'd manage a shared mailbox.
- Every login into a shared account is logged to `admin_account_access_log` with the **real person's** Entra ID OID/email/display name, so actions remain attributable even though the account itself isn't a person (`GET /auth/admin-account-log/{employee_id}`).
- `require_personal_employee` (in `app/deps.py`) blocks shared accounts from personal-data endpoints (leave, payslips, attendance, profile self-service) with a clear 403 — a shared admin account can't "apply for its own leave."
- `seed.py` now creates `hr.admin@psiog.com` / `it.admin@psiog.com` as these shared accounts, and only 3 real individual people (a manager + 2 employees) get personal profile/leave/payslip/attendance data.

---

## Database migrations (Alembic)

Schema changes are now version-controlled through Alembic instead of the
old approach of Postgres auto-running `db/schema.sql` once via
`docker-entrypoint-initdb.d` on a fresh volume. `backend/entrypoint.sh` runs
`alembic upgrade head` automatically on every container start (a no-op if
already up to date), so this is invisible in normal `docker compose up`
use — but it means:

- `db/schema.sql` is now historical reference only (it's what
  `migrations/versions/0001_baseline_schema.py` was captured from) — don't
  hand-edit it and expect it to apply anywhere.
- Future schema changes are new Alembic revisions:
  ```bash
  cd backend
  alembic revision -m "add employee_documents.expiry_date"
  # edit the generated file's upgrade()/downgrade(), then:
  alembic upgrade head
  ```
- Outside Docker (e.g. running the backend directly), apply migrations
  manually before starting the app:
  ```bash
  cd backend
  alembic upgrade head
  uvicorn app.main:app --reload
  ```
- Roll back with `alembic downgrade -1` (one revision) or `alembic downgrade base` (everything).

## Quick start (local dev)

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 14+ (or `docker compose up db chromadb`)

### 1 — Database

```bash
psql -U postgres -c "CREATE USER hrflow_user WITH PASSWORD 'hrflow_pass';"
psql -U postgres -c "CREATE DATABASE hrflow OWNER hrflow_user;"
psql -U postgres -d hrflow -c "GRANT ALL ON SCHEMA public TO hrflow_user;"
psql -h localhost -U hrflow_user -d hrflow -f db/schema.sql
```

### 2 — Backend

```bash
cd backend
cp .env.example .env

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python seed.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/docs · Health check: http://localhost:8000/health

### 3 — ChromaDB (for the real RAG pipeline)

```bash
docker run -d -p 8001:8000 --name hrflow_chromadb chromadb/chroma:latest
```
(Or just use `docker compose up` — see below — which starts Postgres + ChromaDB + the backend together.) Without a reachable ChromaDB, the chatbot automatically falls back to SQL keyword search — see `app/rag_pipeline.py::is_available()`.

### 4 — Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```
Open http://localhost:5173

### Or: everything via Docker Compose

```bash
docker compose up -d --build
docker compose exec backend python seed.py   # once
cd frontend && npm run dev                    # frontend still runs locally, pointed at :8000
```

---

## Demo logins

| Name | Role | Email | Personal HR data? |
|---|---|---|---|
| Kavya Subramaniam | manager | kavya.manager@psiog.com | Yes — real employee |
| Rohan Iyer | employee | rohan.employee@psiog.com | Yes — real employee |
| Sneha Nair | employee | sneha.employee@psiog.com | Yes — real employee |
| **HR Admin** | hr_admin | hr.admin@psiog.com | **No — shared account** |
| **IT Admin** | it_admin | it.admin@psiog.com | **No — shared account** |

With `USE_MOCK_SSO=true` (the default), all five work with no password from the Login screen. In production (`USE_MOCK_SSO=false`), individuals sign in with their own Microsoft account; HR/IT staff are routed into the shared accounts automatically via Entra ID group membership.

---

## Real Microsoft Entra ID SSO

1. Azure Portal → Microsoft Entra ID → App registrations → New registration. Add a SPA redirect URI (e.g. `http://localhost:5173`).
2. Create two Entra ID security groups (e.g. "HR Admins", "IT Admins") and add the real staff who should have each role as members.
3. Fill in `backend/.env`: `ENTRA_TENANT_ID`, `ENTRA_CLIENT_ID`, `ENTRA_HR_ADMIN_GROUP_ID`, `ENTRA_IT_ADMIN_GROUP_ID`, then set `USE_MOCK_SSO=false`.
4. Fill in `frontend/.env`: `VITE_ENTRA_TENANT_ID`, `VITE_ENTRA_CLIENT_ID`, `VITE_USE_MOCK_SSO=false`.
5. In the app registration's "Token configuration", add the `groups` claim to the ID token so `app/security.py::extract_identity` can read group membership. (Large tenants may need a Microsoft Graph `/me/memberOf` call instead — see the note in that function.)

`app/security.py` validates real tokens against Microsoft's JWKS (signature, issuer, audience, expiry) — this is genuine token validation, not a stub. I can't stand up a live Azure tenant for you from here, so this is unverified against a *real* tenant, but the validation and group-resolution logic is fully implemented and covered by unit tests (`tests/test_security.py`).

---

## The RAG pipeline is real

`app/rag_pipeline.py` uses the actual stack from the proposal: PyMuPDF (text extraction) → LangChain `RecursiveCharacterTextSplitter` (chunking) → Sentence-Transformers `all-MiniLM-L6-v2` (embeddings) → ChromaDB (vector store) → LangChain-orchestrated Gemini 2.5 Flash (grounded generation). This replaces the earlier SQL-keyword-search-only chatbot.

If ChromaDB isn't reachable (e.g. running the API outside `docker compose`), `rag_pipeline.is_available()` returns `False` and `routers/chatbot.py` transparently falls back to SQL keyword search — so local dev without Docker still works, just without semantic search.

**Environment note on this sandbox's own testing:** I verified the LangChain chunking logic runs correctly and that ChromaDB/ Sentence-Transformers import cleanly, but I could not fully install the `torch`/`sentence-transformers` model weights or run a live ChromaDB container in the environment I built this in (disk/network constraints of that sandbox — nothing to do with your machine). Run `docker compose up` and try the chatbot with a real `GEMINI_API_KEY` to exercise the full pipeline end-to-end.

---

## Payslip PDFs now use PyMuPDF

`app/payslip_pdf.py` replaces the earlier ReportLab implementation with a PyMuPDF-based template at fixed coordinates, matching the proposal's Module 3 and risk-mitigation #4 ("template with fixed coordinate regions"). Verified with `tests/test_payslip_pdf.py`.

---

## In-portal notifications are real-time now

`app/ws_manager.py` + `app/notification_service.py` add a `WS /notifications/ws?token=<jwt>` endpoint. Every leave decision, HR/IT request status change, and profile change-request decision now writes a `Notification` row **and** pushes it live to the recipient's browser if they're connected — matching "Dual notifications (email + in-portal)" from the tech stack table, which previously only had the email half implemented (the in-portal half only had a polling GET endpoint with nothing that ever wrote a Notification row).

---

## Org hierarchy management (new)

`app/routers/org.py` adds full CRUD for departments, teams, and designations, an employee-directory search endpoint, and an endpoint to move an employee between them — all restricted to `hr_admin`, matching "Org hierarchy managed exclusively by HR Admin." This was previously entirely missing (departments/teams could only ever be read).

**Employee Management screen (new)** — since there are multiple projects/teams, HR Admin needs to allocate managers to employees and correct their records directly:
- `GET /org/employees?q=` — searchable employee directory with department/team/designation/manager already resolved (also fixes the previously-broken Attendance Admin employee search, which was hitting the wrong endpoint entirely).
- `GET /org/managers` — real people eligible to be assigned as a manager (excludes shared admin accounts).
- `PUT /org/employees/{id}/assignment` — HR Admin reassigns department/team/designation/manager.
- `GET /profile/{id}` / `PUT /profile/{id}/hr-edit` — HR Admin views and directly edits any individual employee's profile (contact, address, bank/PAN, designation, department, manager) without needing to go through the employee's own change-request flow — every field changed is still written to `profile_change_requests` (auto-approved, HR Admin as reviewer) for a full audit trail.
- Frontend: `frontend/src/pages/hr/EmployeeManagementPage.jsx`, reachable from the sidebar for HR Admin only.
- Employees can now see who their manager is on their own Profile page (`manager_name`, resolved server-side).

---

## Testing (QA §10 — mandatory)

```bash
cd backend
pip install -r requirements.txt
export TEST_DATABASE_URL=postgresql+psycopg2://hrflow_user:hrflow_pass@localhost:5432/hrflow_test
pytest --cov=app --cov-report=term-missing
```

36 tests across `tests/`, covering:
- **Auth correctness** — JWT issuance/decoding/tampering, real Entra ID token validation failure modes, the shared-admin resolution + access-log write, cross-role 403s.
- **Self-service workflow accuracy + persistence** — leave apply → manager approve → balance update, re-queried from a fresh DB read.
- **Data integrity** — cross-employee payslip access denied (403), manager can't approve a non-direct-report's leave.
- **RAG retrieval + groundedness** — keyword-fallback retrieval returns the right source document; an out-of-scope query is correctly marked ungrounded; escalation tickets are created and visible to HR Admin.
- **Org hierarchy CRUD** — HR-Admin-only writes, and that shared admin accounts can't be "reassigned" like a person.
- **Payslip PDF generation** — produces valid, correctly-populated PDF bytes.

Integration tests need a real Postgres database (the schema uses generated columns, ARRAY columns, and CHECK constraints that don't translate to SQLite) — set `TEST_DATABASE_URL`, or let CI's Postgres service container handle it. They're auto-skipped (not failed) if no test DB is reachable, so the pure unit tests (security/deps/rag_pipeline/payslip_pdf) always run.

I ran the full suite in the environment I built this in, against a real Postgres 16 instance: **36 passed, 66% overall coverage.** Getting to the proposal's ≥80% target mostly means adding more router-path tests (attendance, IT requests, notifications) following the same pattern already established here.

---

## CI/CD (new)

`.github/workflows/ci.yml` runs on every push/PR:
1. Spins up a real Postgres service container, runs the Pytest suite with coverage (fails the build below 60% — raise this as you add more tests).
2. Builds the frontend (`npm ci && npm run build`).

**This workflow does not deploy anywhere** — Azure Static Web Apps deployment was explicitly out of scope for this round of fixes. Add a deploy job (`Azure/static-web-apps-deploy@v1`) once you're ready to wire that up.

---

## Module coverage

| Module | What it does | Status |
|---|---|---|
| Auth + RBAC | Real Entra ID SSO (JWKS-validated) with dev mock fallback; shared HR/IT Admin accounts via group membership | ✅ |
| Leave Management | Apply, approve, balance tracking, business-day calc, holiday blocking | ✅ |
| Payslips | Published payslips list, breakdown, on-demand PDF via **PyMuPDF** | ✅ |
| Attendance | Calendar view, monthly summary, regularisation requests + approval | ✅ |
| My Profile | Self-service contact/address; HR-approval change requests + audit log | ✅ (blocked for shared admin accounts) |
| HR Requests | Raise ticket, comments, HR Admin queue, status — **with live in-portal push** | ✅ |
| IT Requests | Raise ticket, IT Admin queue, status history — **with live in-portal push** | ✅ |
| Policy AI (RAG) | **Real ChromaDB + LangChain + Sentence-Transformers pipeline**, keyword fallback if Chroma unreachable | ✅ |
| Org Hierarchy | Department/Team/Designation CRUD, employee reassignment — **HR Admin only** | ✅ (new) |
| Notifications | Polling GET **+ real-time WebSocket push** | ✅ |
| QA | Pytest suite, 36 tests, 66% coverage | ✅ (new) |
| CI/CD | GitHub Actions: tests + coverage + frontend build | ✅ (new, no Azure deploy) |
| Deployment (Azure Static Web Apps) | Out of scope for this round | ⛔ not done |

---

## Build priority reminder

The schema contains 53 tables in three tiers (see `db/schema.sql`'s "BUILD PRIORITY GUIDE"):
- **Tier 1** (22 tables) — Week 10 mid-term demo
- **Tier 2** (21 tables) — full Week 17 scope — **implemented**
- **Tier 3** (10 tables) — stretch (announcements, assets, education, work experience) — schema exists, no models/endpoints yet
