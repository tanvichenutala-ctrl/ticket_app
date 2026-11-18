# Employee Support Ticket App

## 1. Project Overview & Setup

### Project Overview
The Employee Support Ticket App is a lightweight internal web application built with Python 3.11+, Flask, and SQLite. It provides a secure, role-based ticket management system:
- **Employee**: Can log in, submit support tickets, view and track their own tickets in isolation, edit active tickets, and add comments to their own tickets.
- **Support Staff**: Can log in, view the global ticket queue across all employees, update ticket status through a defined lifecycle (`Open` → `In Progress` → `Resolved` → `Closed`), and post comments on any ticket.

### Windows PowerShell Setup & Run Commands

```powershell
# 1. Navigate to project directory
cd c:\Users\tanvi\Desktop\ticket_app

# 2. Create and activate a Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
# Copy .env.example to .env and configure secrets
Copy-Item .env.example .env
# Ensure SECRET_KEY, EMPLOYEE_PASSWORD, and SUPPORT_PASSWORD are set in .env (or env)

# 5. Initialize database schema and seed demo users & sample tickets
python seed.py

# 6. Run the Flask development server (runs with hot reload in debug mode)
flask --app run run --debug
# The web app is now accessible at http://127.0.0.1:5000

# 7. Run the automated test suite
pytest -v
```

---

## 2. What the AI Generated

### Task 1: Database Schema, Models & Seed Script
- **`schema.sql`**: SQLite schema defining `users`, `tickets`, and `comments` tables with strict check constraints (required non-empty trimmed titles <= 100 characters, non-empty descriptions and comments, enum checks for category, priority, status, and role), foreign keys (`CASCADE` on comments, `RESTRICT` on users), and indexes on `created_by`, `status`, and `ticket_id`.
- **`app/models.py`**: Parameterized database helpers for user creation with `werkzeug.security` password hashing, ticket creation, role-isolated ticket retrieval, ticket editing, support-only status transitions, and comment management.
- **`seed.py`**: Database seeder that securely reads demo passwords from environment variables (`EMPLOYEE_PASSWORD`/`DEMO_EMPLOYEE_PASSWORD` and `SUPPORT_PASSWORD`/`DEMO_STAFF_PASSWORD`), seeds demo accounts (`employee1`, `support1`), and populates the 5 sample tickets from the product prompt.
- **`tests/test_models.py` & `tests/test_seed.py`**: Unit tests verifying schema tables/indexes, password hashing, ticket validation, role isolation, status flows, and seed idempotency.

### Task 2: Authentication & Role-Based Access Control
- **`app/auth.py`**: Blueprint providing `/login` and `/logout` endpoints supporting both JSON API calls and HTML forms. Validates credentials using `check_password_hash`, restricts access to `employee` and `support` roles, and stores session state.
- **Decorators**: `@login_required` (enforces authentication with 401/redirect), `@role_required(*roles)` (enforces role authorization with 403 Forbidden), `@employee_required`, and `@support_required`.
- **`tests/test_auth.py`**: 10 tests verifying valid login for each role, invalid credentials (401), missing fields (400), session logout, and server-side role enforcement.

### Task 3: Ticket Creation, Validation & Role-Based Listing
- **`app/routes.py`**:
  - `GET /tickets`: Displays tickets with strict role filtering (Employees see strictly their own tickets; Support staff see all organization tickets).
  - `GET /tickets/new`: Employee-only form for ticket submission.
  - `POST /tickets/new`: Server-side validation enforcing required title (1–100 characters), required description, category, and priority. Sets initial status to `Open` and records creator ID. Blocks support staff with 403.
- **`tests/test_tickets.py`**: 13 tests covering happy-path creation, support staff denial (403), validation failures (empty/whitespace title, title > 100 chars, empty description, invalid category/priority), role queue isolation, and load performance (< 2s).

### Task 4: Support Status Transitions & Closed Ticket Immutability
- **`app/routes.py`**:
  - `POST /tickets/<id>/status`: Restricted to support staff (`403 Forbidden` for employees). Enforces the unidirectional lifecycle (`Open` → `In Progress` → `Resolved` → `Closed`) and updates `updated_at`.
  - `POST /tickets/<id>/edit`: Employee-only editing of active tickets.
  - **Closed Ticket Lock**: Closed tickets cannot be edited (editing attributes returns 400), and cannot be reopened (status transitions on closed tickets return 400).
  - `GET /tickets/<id>`: Role-authorized ticket detail view.
- **`tests/test_status.py`**: 7 tests verifying support lifecycle status progression, rejection of invalid skips (e.g., Open directly to Closed), employee status rejection (403), and closed ticket edit/reopen prohibition.

### Step 6: Ticket Comments Feature
- **`app/routes.py`**:
  - `POST /tickets/<id>/comments`: Allows employees to comment on their own tickets and support staff to comment on any ticket. Enforces that comments are allowed even when a ticket is `Closed`. Rejects empty or whitespace-only submissions with 400.
  - `GET /tickets/<id>`: Renders comment conversation history in chronological order.
- **`docs/spec_final.md`**: Updated with `AC13: Employee Comment Isolation` and marked Task 6 as completed.
- **`tests/test_comments.py`**: 7 tests verifying employee comments on own tickets, support comments on any ticket, employee comment isolation on other employees' tickets (403), comments on closed tickets, empty comment rejection (400), and unauthenticated rejection (401).

---

## 3. What I Changed (Draft Notes for Personal Rewrite)

<!--
USER NOTE: Use the bullet points below as draft reference material from git history and docs/defect_log.md to rewrite this section in your own words.
-->

- **Repository Initial Configuration**:
  - Added `.gitignore` configured for `.env`, `*.db`, `*.sqlite3`, and `venv/`.
  - Added `.env.example` defining `SECRET_KEY`, `DATABASE_URL`, `EMPLOYEE_PASSWORD`, and `SUPPORT_PASSWORD`.
  - Configured project rules and structural architecture in `AGENT.md`.
- **Specification Refinement**:
  - Created `docs/product_prompt.md` capturing the core business problem and sample ticket cases.
  - Authored `docs/spec_ai_draft.md` and refined it into `docs/spec_final.md` with numbered acceptance criteria (AC1–AC13) and non-functional requirements.
- **Process & Entry Point Management**:
  - Resolved port 5000 conflicts caused by orphaned background processes.
  - Created [run.py](run.py) and updated [app.py](app.py) to properly delegate to the `app/` package for `flask --app run run --debug`.
- **Manual Testing & Defect Logging**:
  - Logged manual test checks in `docs/defect_log.md` covering login, ticket creation, status updates, and closed-ticket handling.
  - Recorded review notes in `docs/review_notes.md` addressing secret auditing and input sanitization boundaries.

---

## 4. What Was Checked

- **Automated Test Suite (`pytest -v`)**:
  - **57 automated tests** across 8 test suites passing at 100%:
    - `tests/test_health.py`: Health check endpoint.
    - `tests/test_models.py`: Database tables, indexes, password hashing, foreign keys, constraints.
    - `tests/test_seed.py`: Seeding idempotency and environment variable handling.
    - `tests/test_auth.py`: Authentication, session persistence, role decorators.
    - `tests/test_tickets.py`: Input validation, ticket submission, role-based ticket isolation.
    - `tests/test_status.py`: Support status lifecycle, employee status prohibition, closed-ticket locking.
    - `tests/test_comments.py`: Comment permissions, closed-ticket comments, comment validation.
    - `tests/test_spec_requirements.py`: End-to-end verification of all core specification requirements.
- **Manual Verification**:
  - Verified browser workflows at `http://127.0.0.1:5000/`:
    - Logged in with demo credentials for both `employee` and `support` roles.
    - Verified employee ticket list isolation (Employee 1 cannot see Employee 2 tickets).
    - Verified support staff can view all tickets and advance statuses.
    - Verified employees cannot change ticket status or edit closed tickets.
    - Verified posting comments on active and closed tickets.
- **Secret & Security Audit**:
  - Verified no hard-coded passwords, secrets, or API keys exist in code; all secrets are loaded dynamically via `os.getenv` / `os.environ`.
  - Passwords hashed using `werkzeug.security` before database persistence.
  - Database queries strictly parameterized to prevent SQL injection.
  - Confirmed `.env` and `*.db` are excluded by `.gitignore`.

---

## 5. Known Gaps & Limitations

1. **Open Redirect in Login**:
   - `request.args.get("next")` is redirected to directly without relative URL validation, creating a potential open redirect risk if an external URL is passed in the query parameter.
2. **Missing Rate Limiting & Unbounded Comment Length**:
   - Comments enforce non-emptiness but lack a maximum character limit.
   - Login and ticket submission endpoints lack rate-limiting.
3. **Missing Pagination**:
   - `GET /tickets` retrieves all records into memory without `LIMIT` / `OFFSET` pagination.
4. **Gitignore File Coverage**:
   - `.gitignore` specifies `.env`, but the project also supports a local private file named `env` (without dot). The `env` file should be explicitly added to `.gitignore`.
5. **Global Error Handling**:
   - Application lacks custom global error pages for `404`, `403`, and `500`, falling back to default Flask/Werkzeug HTML responses.
6. **No Asynchronous Notifications**:
   - Status transitions and comments do not trigger email or push notifications.
