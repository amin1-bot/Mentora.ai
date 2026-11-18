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

## Phase 4: classroom interface

### Running the frontend

Start the backend first (see "Running the backend"), then in a second terminal:
```powershell
cd frontend
npm install        # once, and after dependency changes
npm run dev        # http://localhost:5173
```
Vite forwards every `/api` request to the backend on port 8000, so the browser sees one
site and the login cookies work with no extra setup.

Checks:
```powershell
npm test           # Vitest + React Testing Library
npm run lint       # ESLint
npm run typecheck  # TypeScript
npm run build      # production build into dist/
```

### Screens

| URL | Who | What |
|-----|-----|------|
| `/` | logged out | landing page |
| `/login`, `/signup` | logged out | student login and signup (asks for a guardian email under 18) |
| `/guardian/consent#token=…` | guardian | the link from the email: create account or log in, review, approve |
| `/home` | logged in | student: topics and the "waiting for approval" banner; guardian: placeholder |
| `/classroom` | student | the four zones: topic strip, whiteboard, teacher panel, conversation box. Locked until a guardian approves |
| `/progress` | student | empty until real lessons exist |
| `/settings` | logged in | edit name and grade |

Try the guardian flow locally: sign up a student under 18, copy the consent link printed
in the backend console, log out, and open the link.

### What is real and what is temporary

Since Phase 5 everything on screen is real. The Phase 4 sample lesson
(`sampleLesson.ts`) was deleted when the AI teacher was connected.

### Frontend layout

```
frontend/src/
  app/          main.tsx, router, app shell (header and navigation)
  features/     auth, dashboard, classroom (with whiteboard/), progress, settings
  components/   Button, form fields, Alert, Card, TemporaryBadge
  lib/          api.ts (the only code that calls the backend), error messages
  i18n/         en.ts: every visible sentence lives here
  styles/       tokens.css (colors, spacing, type) and global styles
  types/        TypeScript shapes matching the API
```

### How the whiteboard stays safe

The teacher sends structured blocks (`text`, `step`, `equation`, `question`), never
HTML. `whiteboard/blocks.ts` drops anything malformed or of an unknown type, and a
registry maps each type to a React component. Equations are drawn by KaTeX with
`trust: false`, so LaTeX cannot create links or raw HTML (tested). New abilities in
Phase 7 (graphs, diagrams) are new block types.

KaTeX is used from Phase 4 (the blueprint lists it for Phase 7) because equations are
already one of the MVP block types.

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
python -m app.modules.curriculum.seed    # loads subjects, courses, topics and questions
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/docs. You should see `/api/v1/hello` and `/api/v1/health`.
`/api/v1/health` should say `"database": "ok"`.

Background jobs (reading the text of uploaded PDFs) run inside the API by default, so
nothing else needs starting locally. In production set `JOB_WORKER_IN_API=false` and run
one or more workers next to the API:
```powershell
python -m app.modules.jobs.worker
```

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

## Phase 5: the real AI teacher

The model is the teacher's voice; our code is the teacher's judgment (blueprint section 8).

### Turning it on

1. Create an API key at console.anthropic.com (Settings, API keys) and set a monthly
   spend limit there; that is the hard cap on what the teacher can cost.
2. Put it in `backend/.env` (copy `.env.example` first). Never commit this file:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
3. Restart the backend, start a lesson from Home.

Without a key the classroom says "The AI teacher is not set up on this server yet".

### How one turn works

| Step | Who | File |
|------|-----|------|
| Safety check: distress gets a fixed reply pointing to a trusted adult, never the model; flagged in `audit_log` | code | `teacher/safety.py` |
| Is the message an answer? Check it, spot known misconceptions (25% of 80 = 2000 means "forgot to divide by 100") | code | `adaptive/answers.py` |
| Choose the action: hint ladder, explain differently, solution only after an attempt and all 3 hints, difficulty up after 3 right, down after 2 wrong | code | `adaptive/engine.py` |
| Pick the next question from the approved bank and put it on the board | code | `classroom/repository.py` |
| Fixed rules + grade + the action + recent messages (no names, emails or birth dates) | code | `teacher/prompts.py` |
| Say it well, optionally write steps and equations on the board | model | `ai/providers/anthropic_provider.py` |
| Leak guard: watches the streaming reply and stops any hidden answer before it is shown, then regenerates once; a second leak gets a safe line written by code | code | `teacher/guard.py`, `teacher/generate.py` |
| Save messages, attempt, lesson state, and cost (`ai_requests`, never any text) | code | `classroom/service.py` |

The reply streams to the browser as Server-Sent Events (`POST /sessions/{id}/messages`).

### Model and cost settings (`backend/.env`)

| Setting | Default | Why |
|---------|---------|-----|
| `AI_MODEL` | `claude-opus-5-5` | Most capable current model. `claude-sonnet-5-5` and `claude-haiku-5-5` are cheaper; compare them with the evaluation before switching |
| `AI_EFFORT` | `low` | How much the model thinks before answering. Low keeps replies quick for students |
| `AI_MAX_OUTPUT_TOKENS` | `4000` | Cap per reply, thinking included |
| `DAILY_MESSAGE_LIMIT` | `150` | Per student per day |

Safety fallback is on: if the model declines a request, the API retries it on a suitable
fallback model in the same call (`fallbacks="default"`).

### Measuring the teacher (the Phase 5 gate)

The gate is "a real conversation works and the answer-leak rate is measured on the test
set". With a key in `.env`:
```powershell
cd backend
python -m evaluation.run_eval                              # about 17 replies, a few cents
python -m evaluation.run_eval --model claude-sonnet-5-5   # compare a cheaper model
```
It prints each case and a summary, and saves a report in `evaluation/reports/`:
- **raw leak rate**: how often the model tried to reveal a hidden answer (target under 5%)
- **final leak rate**: how often one reached the student (should be 0)
- fallbacks, median time to first words (target under 2 s), tokens and estimated cost

`evaluation/cases.py` has 17 starter cases, including attempts to talk the teacher into
giving the answer. The blueprint asks for about 50, written by you; add your own there.

### Known limits

- The leak guard catches answers written as numbers, not as words ("twenty"). The
  evaluation counts word leaks separately so we can see whether this happens.
- The distress check is a simple word list; it will miss things and sometimes misfire.
  Flagged messages need human review during the pilot.
- One topic area (Percentages, 15 questions). Mastery that persists between lessons and
  the progress page arrive with the adaptive slice (MVP part of phases 7 and 8).

## Studying with your own documents (multi-subject plan, phases 2–4)

Students aged 18+ upload PDFs in the **Library**. Each PDF is stored privately, its text is
read in the background (pypdf, no AI), split into sections with page numbers and indexed
for full-text search. **Study with Mentora** opens a conversation about one document:

- The teacher sees whole pages, each labelled `[p. N]`: the pages the student names, the
  whole document when it is short, otherwise the best-matching pages.
- Replies cite pages as `[p. N]`. Code removes any citation of a page the teacher was
  not given; in the app each citation opens the PDF at that page.
- When the document does not cover a question, the teacher says so and labels anything
  it adds as general knowledge. Text inside documents is treated as data, never as
  instructions.

**Private documents and free AI plans.** Free plans may keep or train on what they are
sent. Document study therefore only works in local development (with a notice on the
page: use test documents) until `AI_PRIVATE_DOCUMENTS=true` is set in `backend/.env`,
which should only happen with a paid plan that does not train on inputs.

Measuring grounding (uses a made-up sample document, safe on a free plan):
```powershell
python -m evaluation.run_grounding_eval --pause 4
```
Targets: invalid citation rate 0%, and all other scores close to 100%.

**Quizzes (phase 5).** From a document's **Quizzes** page a student asks for 5 to 15
questions (multiple choice, true or false, fill in the blank), a difficulty, a page range
and an optional timer. The AI writes them in the background job queue as structured JSON;
code then checks every question (distinct options, the answer not given away, a fill-in
answer that really appears on the cited page, cited pages that were actually sent) and
asks once more for any that fail. Answers stay on the server until a question is answered,
code grades them, the server enforces the timer, and the report lists the pages to review.
Document quizzes do not change topic mastery yet: that needs a document to be linked to a
catalogue topic, which comes with analytics (phase 9).

Measuring quiz generation (made-up sample document, safe on a free plan):
```powershell
python -m evaluation.run_quiz_eval --runs 3 --pause 4
```
Target: acceptance rate over 85%.

**Study materials (phase 6).** From a document's **Notes & flashcards** page a student
asks for a summary (key points by section), a study guide (overview, key terms,
explanations, self-check questions) or 10 to 40 flashcards, for the whole document or a
page range. They are written in the background, every item is checked to cite pages that
were sent, and each page citation opens the PDF there. Summaries and guides can be printed.
Flashcards are reviewed with spaced repetition: rate each card again / hard / good / easy
and it comes back after 10 minutes, a day, three days, and longer gaps from there.

Measuring material generation (made-up sample document, safe on a free plan):
```powershell
python -m evaluation.run_material_eval --pause 4
```
