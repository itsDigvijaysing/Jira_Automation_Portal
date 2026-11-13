# Jira Automation Portal

A web app that combines a **Jira issue viewer** with an **AI-powered ticket & test-case generator**. From a single free-form requirement it creates a parent Jira ticket, generates 3–5 development tasks, links them to the parent, and generates 3–5 test cases per task as sub-tasks — all driven by Google Gemini.

- **Frontend:** React (Create React App), Tailwind CSS, Framer Motion, Lucide icons.
- **Backend:** Django + Django REST Framework, `requests` (Jira Cloud REST v3), `google-genai` (Gemini).

---

## Table of Contents

1. [Architecture](#architecture)
2. [Project Structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Setup](#setup)
5. [Running](#running)
6. [API Endpoints](#api-endpoints)
7. [How the AI workflow works](#how-the-ai-workflow-works)
8. [Notes & Known Limitations](#notes--known-limitations)

---

## Architecture

```
React SPA (port 3000)  ──HTTP/JSON──>  Django REST API (port 8000)  ──>  Jira Cloud REST v3
                                                  │
                                                  └──>  Google Gemini (google-genai SDK)
```

The single active frontend component is `src/components/JiraAutomationPortal.jsx` (two tabs: **Issues** and **AI Automation**). The backend exposes the API under `/api/`. All Jira and Gemini calls happen server-side using credentials from a `.env` file.

---

## Project Structure

```
.
├── requirements.txt                      # Backend Python dependencies
├── README.md
├── OLD/
│   └── jira-autonomous.py                # Original standalone CLI script (kept for reference; not used by the app)
├── jira_dashboard_backend/               # Django project
│   ├── manage.py
│   ├── .env.example                      # Copy to .env and fill in
│   ├── jira_api/                         # Django app
│   │   ├── services.py                   # JiraService, GeminiService, AutomationService
│   │   ├── views.py                      # DRF endpoints
│   │   └── urls.py
│   └── jira_dashboard/                   # Django settings/urls/asgi/wsgi
│       ├── settings.py
│       └── urls.py
└── jira_dashboard_frontend_c/            # React frontend
    ├── package.json
    ├── .env.example                      # Optional REACT_APP_API_BASE_URL override
    ├── tailwind.config.js
    └── src/
        ├── App.js                        # Renders JiraAutomationPortal
        └── components/JiraAutomationPortal.jsx
```

---

## Prerequisites

- **Python 3.10+** (tested on 3.13) and **Node.js 18+**.
- A **Jira Cloud** account with an API token: https://id.atlassian.com/manage-profile/security/api-tokens
- One or two **Google Gemini API keys** (Gemini Developer API): https://aistudio.google.com/apikey

---

## Setup

### 1. Backend

```bash
cd jira_dashboard_backend
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r ../requirements.txt

cp .env.example .env                # then edit .env with your real values
python manage.py migrate
```

Key `.env` variables (see `.env.example` for the full list):

| Variable | Purpose |
|---|---|
| `SECRET_KEY`, `DEBUG` | Django config |
| `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` | Jira Cloud auth |
| `PROJECT_KEY` | Jira project to read/write (e.g. `SCRUM`) |
| `JIRA_SUBTASK_ISSUE_TYPE` | Sub-task type name (`Subtask` or `Sub-task`) |
| `GEMINI_API_KEY1`, `GEMINI_API_KEY2` | Gemini keys (2nd optional, used for rotation) |
| `GEMINI_MODEL` | Defaults to `gemini-2.5-flash` |

### 2. Frontend

```bash
cd jira_dashboard_frontend_c
npm install
# Optional: echo "REACT_APP_API_BASE_URL=http://localhost:8000" > .env
```

---

## Running

```bash
# Terminal 1 — backend
cd jira_dashboard_backend && source venv/bin/activate
python manage.py runserver            # http://localhost:8000

# Terminal 2 — frontend
cd jira_dashboard_frontend_c
npm start                             # http://localhost:3000
```

Verify Jira connectivity at `http://localhost:8000/api/test/`.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/test/` | Test Jira connection; returns the configured user + projects |
| GET | `/api/issues/` | List issues for the configured project |
| GET | `/api/issues/<key>/` | Issue detail |
| POST | `/api/automation/workflow/` | Run the full AI workflow (`{"requirement": "..."}`) |
| POST | `/api/automation/generate-tasks/` | Generate dev tasks only |
| POST | `/api/automation/generate-tests/` | Generate test cases only |

Issue listing uses Atlassian's current **`/rest/api/3/search/jql`** enhanced-search endpoint (the legacy `/rest/api/3/search` was removed by Atlassian in late 2025).

---

## How the AI workflow works

`AutomationService.create_automated_workflow(requirement)` ([services.py](jira_dashboard_backend/jira_api/services.py)):

1. Create a **parent** Jira Task for the requirement.
2. Ask Gemini for 3–5 **development tasks** (JSON output enforced via `response_mime_type`).
3. Create each as a Jira Task and **link** it to the parent.
4. For each task, ask Gemini for 3–5 **test cases** and create them as **sub-tasks**.
5. Return a status object (parent key, tasks, nested test cases, and any errors).

Resilience: API-key rotation + backoff on Gemini 429/quota errors, and manual fallback tasks/test cases if the AI is unavailable.

---

## Notes & Known Limitations

- **Auth:** the API currently uses `AllowAny`. Do not expose it publicly without adding authentication — the automation endpoints create Jira tickets and consume Gemini quota.
- **Synchronous workflow:** the full workflow runs inline with rate-limit `sleep`s and can take ~30–60s for a large requirement. For production, move it to a background task (Celery/RQ/Channels) and stream progress.
- `OLD/jira-autonomous.py` is the original standalone script and is **not** imported by the app; it's kept for reference only.
