# Mentora: AI Personal Teacher

One FastAPI backend, one React frontend, one PostgreSQL database (see the Phase 1 blueprint).

## Phase 2 setup checklist

Run each install command in PowerShell. Windows will show an admin prompt for some of them.
**Close and reopen your terminal after installing**, so the new commands are found.

| # | Step | Status |
|---|------|--------|
| 1 | Python 3.11+ | Done (3.14.2) |
| 2 | VS Code | Done |
| 3 | Git (2.56) + GitHub repo | Done |
| 4 | Node.js LTS (26.13, npm 11.20) | Done |
| 5 | Docker Desktop (29.9) + PostgreSQL 17 container | Done |
| 6 | Project folder structure | Done |
| 7 | Hello FastAPI endpoint and /docs | Done |
| 8 | Database connection, Alembic, 15 MVP tables, /health checks the database | Done |

## Phase 3: accounts and consent

Gate from the blueprint: *a student provably cannot read another student's data*.
Covered by `test_student_cannot_read_another_students_data` in
`backend/app/tests/test_students.py`.

### Endpoints (all under `/api/v1`)

| Endpoint | Who | What |
|----------|-----|------|
| `POST /auth/signup` | anyone | `account_type` `student` or `guardian`; logs in on success |
| `POST /auth/login` | anyone | email + password |
| `POST /auth/refresh` | logged in | new login cookies; call when a request returns 401 |
| `POST /auth/logout` | logged in | revokes the refresh token, clears cookies |
| `GET`, `PATCH /students/me` | student | own profile (birth date cannot be changed) |
| `GET /students/{id}` | the student, or their approved guardian | everyone else gets 403 |
| `POST /guardians/invite` | student | send or re-send the approval email |
| `POST /guardians/invite-info` | anyone with the link | what the guardian sees before approving |
| `POST /guardians/consent` | guardian | approve, using the token from the email |

Errors always look like `{"error": {"code": "...", "message": "..."}}`.

### Rules currently in place (assumed decisions, change in `app/core/config.py`)

- Students must be **13 or older**. Nothing is stored for younger signups.
- Students **under 18** must give a guardian email. Their `consent_status` stays
  `pending` until the guardian creates an account with that same email and approves.
- Passwords: Argon2id hashes, at least 10 characters, cannot contain the email name.
- 5 wrong passwords lock the account for 15 minutes. Signup and login are limited to
  10 tries per minute per IP address.

### How login works (for the frontend in Phase 4)

- Login sets three cookies. The access and refresh cookies are `HttpOnly`, so JavaScript
  cannot read them (protects against stolen tokens).
- Send requests with `credentials: "include"`. For every `POST`, `PATCH` and `DELETE`,
  copy the `mentora_csrf` cookie into an `X-CSRF-Token` header.
- The access cookie lasts 15 minutes. On a 401, call `POST /auth/refresh` once, then retry.
- Each refresh token works once. If an old one is reused, every session of that user ends.

### Known gaps (to do before real students)

- **No real email yet.** Locally, the consent link is printed in the server console.
  The server refuses to start sending email in staging or production until a provider
  is added (`app/core/email.py`).
- **Consent text not written.** `CONSENT_VERSION` is `2026-11-draft`; the wording of what
  guardians agree to needs legal review (blueprint section 10).
- Guardians cannot yet revoke consent or delete the account (parent dashboard, Phase 12).
- Rate limits are counted in memory per server process; Redis comes in Phase 13.
- Students with `pending` consent can log in and edit their profile. Lessons (Phase 5)
  must check `consent_status` before teaching.

### 3. Git
Git records every change to your code so you can undo mistakes and push to GitHub.

```powershell
winget install --id Git.Git -e
```
Check it worked (in a new terminal): `git --version`

Then tell Git who you are (shown on your commits):
```powershell
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```
Create a free account at github.com and a new **empty** repository named `ai-teacher`
(no README, no .gitignore; we already have those).

### 4. Node.js LTS
Node runs JavaScript tools on your computer. We need it for Vite and React in Phase 4.

```powershell
winget install --id OpenJS.NodeJS.LTS -e
```
Check: `node --version` and `npm --version`

### 5. Docker Desktop
Docker runs PostgreSQL in a packaged container, the same on your laptop as on the server.

```powershell
winget install --id Docker.DockerDesktop -e
```
Docker needs WSL 2 and usually asks for a restart. After restarting, open Docker Desktop once
and wait until it says "Engine running". Check: `docker --version` and `docker run hello-world`

Then start the database from this folder:
```powershell
docker compose up -d
docker compose ps        # "db" should show (healthy)
```

### VS Code extensions
Open this folder in VS Code (`code .`). It will offer the recommended extensions
(Python, Ruff, Docker, ESLint). Click Install.

## Running the backend

```powershell
cd backend
python -m venv .venv                     # once
.\.venv\Scripts\Activate.ps1             # every new terminal
pip install -e ".[dev]"                  # once, and after dependency changes
copy .env.example .env                   # once
docker compose up -d                     # from the ai-teacher folder: starts PostgreSQL
alembic upgrade head                     # creates or updates the tables
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs. You should see `/api/v1/hello` and `/api/v1/health`.
`/api/v1/health` should say `"database": "ok"`.

Tests and lint (Docker must be running). Tests use their own `mentora_test` database,
created and migrated automatically, and emptied before every test:
```powershell
pytest
ruff check .
```

## Changing the database

Never edit tables by hand. Change a `models.py`, then:
```powershell
alembic revision --autogenerate -m "describe the change"   # writes a migration file
# read the new file in alembic/versions before applying it
alembic upgrade head                                         # applies it
alembic downgrade -1                                         # undoes the last one if needed
```
A new `models.py` file must also be imported in `app/db_models.py`, or Alembic won't see it.

If PowerShell refuses to run `Activate.ps1`, run once:
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## Layout

```
backend/app/
  main.py        creates the app, registers routers
  core/          config, security, database, logging, errors
  modules/       auth, students, curriculum, classroom, teacher, adaptive, progress
  ai/            AI provider interface (base.py) and one file per vendor
  tests/
backend/alembic/ database migrations (set up once Docker works)
frontend/src/    React app skeleton (created with Vite in Phase 4)
```
