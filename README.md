# Jira Automation Portal

**Jira Automation Portal** is a web application designed to streamline Jira ticket management and sprint planning. It combines:

1. **Issue Viewer** — a React + Django interface for browsing and inspecting existing Jira issues.  
2. **AI-Powered Ticket & Test-Case Generator** — a Python pipeline (to be integrated into Django) that uses the Google Gemini API to automatically generate development subtasks and test-case subtasks from high-level requirements.

---

## Table of Contents

1. [Core Features](#core-features)  
2. [Technology Stack](#technology-stack)  
3. [File Structure](#file-structure)  
4. [Prerequisites](#prerequisites)  
5. [Setup & Installation](#setup--installation)  
6. [Running the Application](#running-the-application)  
7. [Integration Plan](#integration-plan)  
8. [Core Functions](#core-functions)  
9. [Error Handling](#error-handling)  
10. [Extensibility](#extensibility)  

---

## Core Features

### A. Issue Viewer (Implemented)

- **Fetch & List Issues**: Displays all issues from a configured Jira project (default: `SCRUM`), showing issue key, summary, status, and assignee.  
- **Detail View**: Shows description, issue type, priority, creation date, and other fields.

### B. AI-Powered Ticket & Test-Case Generation (Standalone)

- **Requirement Agent**  
  1. Prompts Google Gemini API to generate 3–5 high-level development subtasks from a free-form requirement.  
  2. Creates each subtask as a Jira issue via REST API and links them to a parent ticket.  
- **Test Agent**  
  1. For each development task, prompts Gemini to generate 3–5 detailed test cases.  
  2. Creates them as Jira subtasks under their respective development tasks.  
- **Features**: API-key rotation, rate-limit backoff, JSON parsing, and issue linking.

---

## Technology Stack

- **Frontend**  
  - React.js, Lucide React, Framer Motion, Tailwind CSS  
  - Node.js (development server & build)  

- **Backend**  
  - Django, Django REST Framework, django-cors-headers  

- **AI & Automation**  
  - Python 3.9+, `google-generativeai`, `requests`, `python-dotenv`  

- **Jira Integration**  
  - Jira Cloud/Server REST API  
---

## File Structure

```
.
├── .git/                              # Git metadata
├── .gitignore
├── jira-autonomous.py                # Standalone AI ticket & test-case generator
├── jira\_dashboard\_backend/           # Django backend app
│   ├── manage.py
│   ├── jira\_api/                     # Django app for Jira interactions
│   │   ├── views.py                  # Issue-fetch & (future) AI endpoints
│   │   └── urls.py
│   ├── your\_project\_name/            # Django project settings
│   │   ├── settings.py
│   │   └── urls.py
│   └── .env                          # Backend environment variables
├── jira\_dashboard\_frontend\_c/        # React frontend
│   ├── package.json
│   ├── public/
│   └── src/
│       └── JiraIssueTracker.jsx      # Main component for issue browsing
└── README.md

```

---

## Prerequisites

- **Node.js** & **npm** (or yarn)  
- **Python 3.8+** & **pip**  
- **Jira** Cloud or Server account:  
  - Email & API token  
  - Base URL (e.g., `https://your-domain.atlassian.net`)  
- **Google Gemini API key(s)**  
- **Git**

---

## Setup & Installation

1. **Clone repository**  
   ```bash
   git clone <repo-url>
   cd Jira_Automation_Portal

2. **Backend (Django)**

   ```bash
   cd jira_dashboard_backend
   python -m venv venv
   source venv/bin/activate          # Windows: venv\Scripts\activate
   pip install django djangorestframework \
               requests python-dotenv \
               django-cors-headers google-generativeai
   ```

   * Create a `.env` file in `jira_dashboard_backend`:

     ```env
     SECRET_KEY=your_django_secret_key
     DEBUG=True
     JIRA_URL=https://your-domain.atlassian.net
     JIRA_EMAIL=your-email@example.com
     JIRA_API_TOKEN=your_jira_api_token
     GEMINI_API_KEY1=your_first_gemini_key
     GEMINI_API_KEY2=your_second_gemini_key
     ```
   * In `settings.py`:

     * Load `.env` (e.g., via `python-dotenv` or `django-environ`).
     * Add `'corsheaders'` to `INSTALLED_APPS` and `'corsheaders.middleware.CorsMiddleware'` to `MIDDLEWARE`.
     * Set `CORS_ALLOWED_ORIGINS = ["http://localhost:3000"]`.
   * Apply migrations:

     ```bash
     python manage.py migrate
     ```

3. **Frontend (React)**

   ```bash
   cd ../jira_dashboard_frontend_c
   npm install                       # or yarn install
   ```

4. **Standalone AI Script**

   * Ensure `jira-autonomous.py` and a `.env` in the project root contain:

     ```env
     JIRA_EMAIL=your-email@example.com
     JIRA_API_TOKEN=your_jira_api_token
     JIRA_BASE_URL=https://your-domain.atlassian.net
     PROJECT_KEY=YOUR_JIRA_PROJECT_KEY
     GEMINI_API_KEY1=your_first_gemini_key
     GEMINI_API_KEY2=your_second_gemini_key
     ```

---

## Running the Application

1. **Start Django**

   ```bash
   cd jira_dashboard_backend
   source venv/bin/activate
   python manage.py runserver         # http://localhost:8000
   ```

2. **Start React**

   ```bash
   cd ../jira_dashboard_frontend_c
   npm start                          # http://localhost:3000
   ```

3. **Test the AI Script (Standalone)**

   ```bash
   cd ..
   python jira-autonomous.py
   ```

   * Enter a requirement when prompted.
   * Verify creation of parent ticket, development subtasks, and test-case subtasks in Jira.

---

## Integration Plan

1. **Refactor** `jira-autonomous.py` into modular functions.
2. **Expose** them via new Django REST endpoints (e.g., `/api/create-ai-tasks/`).
3. **Update Frontend**:

   * Add an input form or PDF upload component.
   * Call the new endpoints and display real-time feedback (via WebSockets or polling).

---

## Core Functions

* **`generate_content_with_fallback(prompt: str) -> str`**
  Handles Gemini API calls with retry and key rotation.

* **`generate_development_tasks(requirement: str) -> list`**
  Generates and parses 3–5 development task descriptions from the requirement.

* **`create_jira_ticket(summary: str, description: str) -> str`**
  Creates a Jira issue and returns its key.

* **`generate_and_create_test_cases(task_description: str, task_key: str) -> list`**
  Generates test cases for a task and creates them as Jira subtasks.

* **`create_jira_subtask(parent_key: str, summary: str, description: str) -> str`**
  Creates a subtask under a given parent issue.

* **`fetch_visible_tickets() -> list`**
  Retrieves all non-sample issues from the configured project.

---

## Error Handling

* **JSON Parsing**: Logs raw AI responses when parsing fails.
* **API Retries**: Retries Jira and Gemini calls up to 3 times on failures.
* **Key Rotation**: Automatically switches Gemini API keys upon rate-limit or quota errors.
---