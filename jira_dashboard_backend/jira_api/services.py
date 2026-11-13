# jira_api/services.py
import requests
from requests.auth import HTTPBasicAuth
import json
import time
import threading
from google import genai
from google.genai import types
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
import logging

logger = logging.getLogger(__name__)

class JiraAPIError(Exception):
    """A failed Jira call, carrying Jira's own error text and HTTP status."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class JiraService:
    """Service class for Jira API interactions"""

    # Fields requested for the issue list / detail views.
    LIST_FIELDS = "summary,status,assignee,issuetype,priority,created,description,updated,reporter"
    # (connect, read) seconds. Without a timeout a stalled Jira call hangs the worker forever.
    TIMEOUT = (10, 30)
    # Jira rejects summaries longer than 255 characters or containing newlines.
    SUMMARY_MAX_LENGTH = 255

    def __init__(self):
        missing = [
            name for name, value in (
                ("JIRA_URL", settings.JIRA_BASE_URL),
                ("JIRA_EMAIL", settings.JIRA_EMAIL),
                ("JIRA_API_TOKEN", settings.JIRA_API_TOKEN),
            ) if not value
        ]
        if missing:
            raise ImproperlyConfigured(
                f"Missing Jira settings: {', '.join(missing)}. Set them in jira_dashboard_backend/.env."
            )

        self.email = settings.JIRA_EMAIL
        self.api_token = settings.JIRA_API_TOKEN
        self.base_url = settings.JIRA_BASE_URL.rstrip("/")
        self.project_key = settings.JIRA_PROJECT_KEY
        self.max_results = getattr(settings, 'JIRA_MAX_RESULTS', 50)
        self.subtask_issue_type = getattr(settings, 'JIRA_SUBTASK_ISSUE_TYPE', 'Subtask')
        self.auth = HTTPBasicAuth(self.email, self.api_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    @staticmethod
    def _error_detail(response):
        """Pull Jira's human-readable error out of a failed response."""
        try:
            body = response.json()
        except ValueError:
            return response.text.strip()[:300] or response.reason
        if not isinstance(body, dict):
            return str(body)[:300]
        parts = list(body.get("errorMessages") or [])
        errors = body.get("errors")
        if isinstance(errors, dict):
            parts.extend(f"{field}: {message}" for field, message in errors.items())
        if not parts and body.get("message"):
            parts.append(str(body["message"]))
        return "; ".join(str(part) for part in parts) or response.reason

    def _request(self, method, path, **kwargs):
        """Call the Jira REST API; raise JiraAPIError with Jira's message on failure."""
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method, url, headers=self.headers, auth=self.auth, timeout=self.TIMEOUT, **kwargs
            )
        except requests.exceptions.RequestException as e:
            logger.error(f"Jira request failed ({method} {path}): {e}")
            raise JiraAPIError(f"Could not reach Jira: {e}") from e

        if not response.ok:
            detail = self._error_detail(response)
            logger.error(f"Jira {method} {path} returned {response.status_code}: {detail}")
            raise JiraAPIError(f"Jira returned {response.status_code}: {detail}", response.status_code)
        return response

    @classmethod
    def _clean_summary(cls, summary):
        """Make a string a valid Jira summary: one line, at most 255 characters."""
        text = " ".join(str(summary or "").split()) or "Untitled"
        if len(text) > cls.SUMMARY_MAX_LENGTH:
            text = text[:cls.SUMMARY_MAX_LENGTH - 3].rstrip() + "..."
        return text

    @staticmethod
    def _to_adf(text):
        """Convert plain text to an Atlassian Document Format doc.

        Blank lines become paragraph breaks and single newlines hard breaks
        (a raw newline inside a text node is not rendered as a line break).
        Returns None for empty text: ADF text nodes must not be empty.
        """
        paragraphs = []
        for block in str(text or "").replace("\r\n", "\n").split("\n\n"):
            lines = [line for line in block.split("\n") if line.strip()]
            if not lines:
                continue
            content = []
            for index, line in enumerate(lines):
                if index:
                    content.append({"type": "hardBreak"})
                content.append({"type": "text", "text": line})
            paragraphs.append({"type": "paragraph", "content": content})
        if not paragraphs:
            return None
        return {"type": "doc", "version": 1, "content": paragraphs}

    def _search_jql(self, jql, limit):
        """Page through the enhanced JQL search endpoint and collect issues.

        Atlassian removed GET/POST ``/rest/api/3/search`` (HTTP 410 Gone) on
        2025-10-31. The replacement ``/rest/api/3/search/jql`` paginates with
        ``nextPageToken`` instead of ``startAt``, no longer returns ``total``
        and rejects unbounded JQL (a query with no restriction such as a project).
        """
        issues = []
        next_page_token = None

        while len(issues) < limit:
            params = {
                "jql": jql,
                "maxResults": min(100, limit - len(issues)),
                "fields": self.LIST_FIELDS,
            }
            if next_page_token:
                params["nextPageToken"] = next_page_token

            data = self._request("GET", "/rest/api/3/search/jql", params=params).json()

            page = data.get("issues", [])
            issues.extend(page)
            next_page_token = data.get("nextPageToken")
            if data.get("isLast") or not next_page_token or not page:
                break

        return issues[:limit]

    def fetch_issues(self, max_results=None):
        """Fetch issues for the configured project, newest first."""
        limit = max_results or self.max_results
        jql = f'project = "{self.project_key}" ORDER BY created DESC'

        logger.info(f"Fetching issues with JQL: {jql}")
        issues = self._search_jql(jql, limit)
        return {"issues": issues, "count": len(issues)}

    def fetch_issue_details(self, issue_key):
        """Fetch detailed information for a specific issue"""
        return self._request("GET", f"/rest/api/3/issue/{issue_key}").json()

    def get_myself(self):
        """Return the Jira user the configured credentials belong to."""
        return self._request("GET", "/rest/api/3/myself").json()

    def get_projects(self, limit=10):
        """Return up to ``limit`` projects visible to the configured user."""
        data = self._request("GET", "/rest/api/3/project/search", params={"maxResults": limit}).json()
        return data.get("values", [])

    def create_issue(self, summary, description, issue_type="Task", parent_key=None):
        """Create a new Jira issue.

        ``issue_type="Subtask"`` is treated as a request for a sub-task and is
        mapped to the project's configured sub-task type name.
        """
        is_subtask = issue_type == "Subtask"
        resolved_type = self.subtask_issue_type if is_subtask else issue_type

        fields = {
            "project": {"key": self.project_key},
            "summary": self._clean_summary(summary),
            "issuetype": {"name": resolved_type},
        }
        adf_description = self._to_adf(description)
        if adf_description:
            fields["description"] = adf_description

        # Add parent key if creating a subtask
        if parent_key and is_subtask:
            fields["parent"] = {"key": parent_key}

        return self._request("POST", "/rest/api/3/issue", json={"fields": fields}).json()

    def link_issues(self, outward_issue, inward_issue, link_type="Relates"):
        """Link two Jira issues. Returns True on success, False otherwise."""
        payload = {
            "outwardIssue": {"key": outward_issue},
            "inwardIssue": {"key": inward_issue},
            "type": {"name": link_type}
        }

        try:
            self._request("POST", "/rest/api/3/issueLink", json=payload)
            return True
        except JiraAPIError:
            return False

    def get_link_types(self):
        """Get available issue link types"""
        try:
            return self._request("GET", "/rest/api/3/issueLinkType").json().get("issueLinkTypes", [])
        except JiraAPIError:
            return []


class GeminiService:
    """Service class for Google Gemini API interactions.

    Uses the unified ``google-genai`` SDK (the legacy ``google-generativeai``
    SDK reached end-of-support on 2025-11-30). Keeps the original key-rotation
    behaviour and forces JSON output via ``response_mime_type``.
    """

    def __init__(self):
        self.api_keys = [k for k in (settings.GEMINI_API_KEY1, settings.GEMINI_API_KEY2) if k]
        if not self.api_keys:
            raise ImproperlyConfigured(
                "No Gemini API keys configured. Set GEMINI_API_KEY1 (and optionally GEMINI_API_KEY2)."
            )
        self.model = getattr(settings, 'GEMINI_MODEL', 'gemini-2.5-flash')
        self.current_key_index = 0
        # Serialize generation/key-rotation: this service is shared as a
        # singleton and Django's dev server (and threaded WSGI) is multi-threaded.
        self._lock = threading.Lock()
        self._client = self._make_client()

    def _make_client(self):
        """Build a client bound to the current API key."""
        return genai.Client(api_key=self.api_keys[self.current_key_index])

    def _rotate_key(self):
        """Rotate to next API key and rebuild the client."""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self._client = self._make_client()

    def generate_content(self, prompt, retry_count=3):
        """Generate JSON content with automatic key rotation on failure."""
        attempts = 0
        last_error = None
        max_attempts = len(self.api_keys) * retry_count

        with self._lock:
            while attempts < max_attempts:
                try:
                    response = self._client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                        ),
                    )
                    text = response.text
                    # response.text is None on a safety block or MAX_TOKENS
                    # truncation — treat as a failure so we retry/rotate.
                    if not text:
                        raise RuntimeError("Empty Gemini response (safety block or truncation)")
                    return text
                except Exception as e:
                    last_error = e
                    logger.warning(f"Gemini API error with key index {self.current_key_index}: {e}")

                    attempts += 1
                    if attempts >= max_attempts:
                        break

                    err = str(e).lower()
                    if '429' in err or 'quota' in err or 'resource_exhausted' in err:
                        # Wait longer for rate-limit / quota issues
                        time.sleep(5)

                    self._rotate_key()

                    if attempts % len(self.api_keys) == 0:
                        time.sleep(10)  # Longer wait between full rotations

        raise Exception(f"All Gemini API keys failed: {last_error}")

    def parse_json_response(self, response_text):
        """Extract and parse JSON from a model response, tolerant of fences/prose."""
        if not response_text:
            return None

        text = response_text.strip()

        # Strip a leading ```json / ``` code fence if present
        if text.startswith("```"):
            text = text[3:]
            if text[:4].lower() == "json":
                text = text[4:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        # 1) Try a direct parse (the common case with response_mime_type=json)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 2) Fall back to extracting the outermost array or object
        for open_ch, close_ch in (("[", "]"), ("{", "}")):
            start = text.find(open_ch)
            end = text.rfind(close_ch)
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    continue

        logger.error(f"Error parsing JSON. Raw response: {response_text}")
        return None


class AutomationService:
    """Service for AI-powered Jira automation"""
    
    def __init__(self):
        self.jira = JiraService()
        self.gemini = GeminiService()
    
    def _generate_items(self, prompt):
        """Run a prompt and return the model's answer as a list of dicts.

        The prompts ask for a JSON array, but models sometimes wrap it in an
        object (``{"tasks": [...]}``) or return a single object.
        """
        parsed = self.gemini.parse_json_response(self.gemini.generate_content(prompt))
        if isinstance(parsed, dict):
            nested = next((value for value in parsed.values() if isinstance(value, list)), None)
            parsed = nested if nested is not None else [parsed]
        if not isinstance(parsed, list):
            return []
        return [item for item in parsed if isinstance(item, dict)]

    @staticmethod
    def _is_quota_error(error):
        text = str(error).lower()
        return "429" in text or "quota" in text or "resource_exhausted" in text

    def generate_development_tasks(self, requirement):
        """Generate development subtasks for a requirement"""
        prompt = f"""Analyze the following software development task and generate EXACTLY 3 to 5 high-level, non-overlapping subtasks:
Task: {requirement}

Instructions:
1. Generate EXACTLY 3 to 5 distinct subtasks - no more, no less.
2. Each subtask should represent a major component or phase of development.
3. Ensure subtasks are broad enough to encompass significant work but specific enough to be actionable.
4. Focus on different aspects (e.g., one backend, one frontend, one for testing) rather than breaking down the same component.
5. Ensure NO DUPLICATION or overlap between subtasks.
6. Provide a category for each task (e.g., Backend, Frontend, API Integration, DevOps, Testing).
7. Predict a module or component name if possible.
8. Each subtask summary should be comprehensive but under 100 words.

Output the result as JSON in exactly this format:
[
  {{
    "summary": "Subtask summary in under 100 words",
    "category": "Backend | Frontend | API | DevOps | Testing",
    "component": "Suggested component/module",
    "title": "Short title for the Jira ticket"
  }}
]

IMPORTANT: Verify that each subtask is unique and distinct before finalizing the output. The total number of subtasks MUST be between 3 and 5, inclusive."""
        
        return self._generate_items(prompt)
    
    def generate_test_cases(self, task_description):
        """Generate test cases for a development task"""
        prompt = f"""Generate EXACTLY 3 to 5 comprehensive test cases for the following development task:

Task Description: {task_description}

Instructions:
1. Generate EXACTLY 3 to 5 test cases - no more, no less.
2. Each test case should cover a critical functionality or edge case.
3. Test cases should be specific, actionable, and verifiable.
4. Include expected results and acceptance criteria.
5. Focus on different aspects of the task to ensure comprehensive coverage.
6. Ensure test cases are meaningful and not trivial.

Output the result as JSON in exactly this format:
[
  {{
    "test_id": "TC-1",
    "test_name": "Short descriptive name",
    "description": "Detailed test case description",
    "steps": ["Step 1", "Step 2", "Step 3"],
    "expected_result": "Expected outcome of the test",
    "priority": "High | Medium | Low"
  }}
]

IMPORTANT: Make sure each test case is unique and thorough. The total number of test cases MUST be between 3 and 5, inclusive."""
        
        return self._generate_items(prompt)
    
    def create_automated_workflow(self, requirement):
        """Create complete automated workflow with parent ticket, dev tasks, and test cases.

        A failure on one ticket is recorded in ``errors`` and the rest of the
        workflow carries on, so the result always reflects what exists in Jira.
        """
        workflow_status = {
            "requirement": requirement,
            "parent_ticket": None,
            "development_tasks": [],
            "test_cases": {},
            "errors": []
        }
        errors = workflow_status["errors"]

        try:
            # Step 1: Create parent ticket
            parent_result = self.jira.create_issue(
                f"Main Task: {requirement}",
                f"This is the parent ticket for:\n\n{requirement}\n\nDevelopment tasks will be linked to this ticket.",
                "Task"
            )
            parent_key = parent_result.get("key")
            workflow_status["parent_ticket"] = parent_key

            if not parent_key:
                errors.append("Failed to create parent ticket")
                return workflow_status

            # Step 2: Generate development tasks
            logger.info("Generating development tasks...")
            time.sleep(2)  # Rate limiting before AI call

            try:
                dev_tasks = self.generate_development_tasks(requirement)
            except Exception as e:
                if self._is_quota_error(e):
                    errors.append("AI service quota exceeded. Using fallback task generation.")
                    dev_tasks = self._create_fallback_tasks(requirement)
                else:
                    errors.append(f"Failed to generate development tasks: {e}")
                    return workflow_status

            if not dev_tasks:
                errors.append("No development tasks generated")
                return workflow_status

            # Get available link types
            link_types = self.jira.get_link_types()
            link_type = "Relates"
            if link_types:
                available_names = [lt.get("name") for lt in link_types]
                for lt in ["Relates", "Relates to", "Dependency"]:
                    if lt in available_names:
                        link_type = lt
                        break

            # Set once a sub-task is rejected as a bad request: the same
            # request would fail for every remaining test case.
            subtasks_rejected = False

            for index, task in enumerate(dev_tasks, start=1):
                title = str(task.get("title") or task.get("summary") or f"Development task {index}")
                summary = str(task.get("summary") or title)
                category = str(task.get("category") or "General")
                component = str(task.get("component") or "Unspecified")

                description = (f"{summary}\n\n"
                               f"Category: {category}\n"
                               f"Component: {component}\n"
                               f"Parent Task: {parent_key}")

                try:
                    task_key = self.jira.create_issue(title, description, "Task").get("key")
                except JiraAPIError as e:
                    errors.append(f"Failed to create development task '{title}': {e}")
                    continue
                if not task_key:
                    errors.append(f"Jira returned no key for development task '{title}'")
                    continue

                workflow_status["development_tasks"].append({
                    "key": task_key,
                    "title": title,
                    "summary": summary,
                    "category": category
                })

                if not self.jira.link_issues(parent_key, task_key, link_type):
                    errors.append(f"Could not link {task_key} to {parent_key}")

                if subtasks_rejected:
                    continue

                # Step 3: Generate and create test cases for this task
                time.sleep(3)  # Rate limiting

                try:
                    test_cases = self.generate_test_cases(summary)
                except Exception as e:
                    if self._is_quota_error(e):
                        errors.append(f"AI quota exceeded for test cases of {task_key}. Using fallback test cases.")
                        test_cases = self._create_fallback_test_cases(title)
                    else:
                        errors.append(f"Failed to generate test cases for {task_key}: {e}")
                        continue

                if not test_cases:
                    errors.append(f"No test cases generated for {task_key}")
                    continue

                created = workflow_status["test_cases"][task_key] = []

                for tc in test_cases:
                    name = str(tc.get("test_name") or "Basic Test")
                    priority = str(tc.get("priority") or "Medium")
                    steps = tc.get("steps") or ["Execute test"]
                    if not isinstance(steps, list):
                        steps = [steps]
                    steps_formatted = "\n".join(f"{n}. {step}" for n, step in enumerate(steps, start=1))

                    tc_description = (
                        f"Test Case: {name}\n\n"
                        f"Description: {tc.get('description') or 'Test the functionality'}\n\n"
                        f"Steps:\n{steps_formatted}\n\n"
                        f"Expected Result: {tc.get('expected_result') or 'Functionality works as expected'}\n\n"
                        f"Priority: {priority}"
                    )

                    try:
                        tc_key = self.jira.create_issue(
                            f"Test: {name} [{priority}]", tc_description, "Subtask", task_key
                        ).get("key")
                    except JiraAPIError as e:
                        errors.append(f"Failed to create test case '{name}' under {task_key}: {e}")
                        if e.status_code == 400:
                            subtasks_rejected = True
                            errors.append(
                                "Jira rejected the sub-task, so the remaining test cases were skipped. "
                                f"Check that JIRA_SUBTASK_ISSUE_TYPE ('{self.jira.subtask_issue_type}') "
                                "matches the sub-task type name in your project."
                            )
                            break
                        continue

                    if tc_key:
                        created.append({"key": tc_key, "name": name, "priority": priority})

                    time.sleep(2)  # Rate limiting

        except Exception as e:
            errors.append(str(e))
            logger.exception("Automation workflow error")

        return workflow_status

    def _create_fallback_tasks(self, requirement):
        """Create basic fallback tasks when AI is unavailable"""
        return [
            {
                "title": f"Backend Development for {requirement[:50]}...",
                "summary": f"Develop the backend components and API endpoints for: {requirement}",
                "category": "Backend",
                "component": "API"
            },
            {
                "title": f"Frontend Development for {requirement[:50]}...",
                "summary": f"Create the user interface and frontend components for: {requirement}",
                "category": "Frontend", 
                "component": "UI"
            },
            {
                "title": f"Testing & Integration for {requirement[:50]}...",
                "summary": f"Create comprehensive tests and handle integration for: {requirement}",
                "category": "Testing",
                "component": "QA"
            }
        ]
    
    def _create_fallback_test_cases(self, task_title):
        """Create basic fallback test cases when AI is unavailable"""
        return [
            {
                "test_name": f"Basic Functionality Test for {task_title}",
                "description": f"Test the core functionality of {task_title}",
                "steps": ["Execute the main feature", "Verify output", "Check for errors"],
                "expected_result": "Feature works correctly without errors",
                "priority": "High"
            },
            {
                "test_name": f"Edge Case Test for {task_title}",
                "description": f"Test edge cases and boundary conditions for {task_title}",
                "steps": ["Test with edge case inputs", "Verify handling", "Check system stability"],
                "expected_result": "System handles edge cases gracefully",
                "priority": "Medium"
            }
        ]