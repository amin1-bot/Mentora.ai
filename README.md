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

Tests and lint (the database must be running and migrated):
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
