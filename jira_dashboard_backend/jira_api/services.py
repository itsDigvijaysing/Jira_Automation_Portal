# jira_api/services.py
import requests
from requests.auth import HTTPBasicAuth
import json
import time
import google.generativeai as genai
import os
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class JiraService:
    """Service class for Jira API interactions"""
    
    def __init__(self):
        self.email = settings.JIRA_EMAIL
        self.api_token = settings.JIRA_API_TOKEN
        self.base_url = settings.JIRA_BASE_URL
        self.project_key = settings.JIRA_PROJECT_KEY
        self.auth = HTTPBasicAuth(self.email, self.api_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def fetch_issues(self, max_results=50):
        """Fetch all issues from the project"""
        url = f"{self.base_url}/rest/api/3/search"
        params = {
            "jql": f"project = {self.project_key} ORDER BY created DESC",
            "maxResults": max_results,
            "fields": "summary,status,assignee,issuetype,priority,created,description,updated,reporter"
        }
        
        try:
            logger.info(f"Fetching issues with JQL: {params['jql']}")
            response = requests.get(url, headers=self.headers, params=params, auth=self.auth)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching issues: {e}")
            # If the project key doesn't exist, try fetching all accessible issues
            if "400" in str(e):
                logger.warning(f"Project key {self.project_key} might not exist. Trying to fetch all accessible issues.")
                params["jql"] = "ORDER BY created DESC"
                try:
                    response = requests.get(url, headers=self.headers, params=params, auth=self.auth)
                    response.raise_for_status()
                    return response.json()
                except requests.exceptions.RequestException as fallback_error:
                    logger.error(f"Fallback query also failed: {fallback_error}")
            raise
    
    def fetch_issue_details(self, issue_key):
        """Fetch detailed information for a specific issue"""
        url = f"{self.base_url}/rest/api/3/issue/{issue_key}"
        
        try:
            response = requests.get(url, headers=self.headers, auth=self.auth)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching issue {issue_key}: {e}")
            raise
    
    def create_issue(self, summary, description, issue_type="Task", parent_key=None):
        """Create a new Jira issue"""
        url = f"{self.base_url}/rest/api/3/issue"
        
        payload = {
            "fields": {
                "project": {"key": self.project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": description
                                }
                            ]
                        }
                    ]
                },
                "issuetype": {"name": issue_type}
            }
        }
        
        # Add parent key if creating a subtask
        if parent_key and issue_type == "Subtask":
            payload["fields"]["parent"] = {"key": parent_key}
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, auth=self.auth)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error creating issue: {e}")
            raise
    
    def link_issues(self, outward_issue, inward_issue, link_type="Relates"):
        """Link two Jira issues"""
        url = f"{self.base_url}/rest/api/3/issueLink"
        
        payload = {
            "outwardIssue": {"key": outward_issue},
            "inwardIssue": {"key": inward_issue},
            "type": {"name": link_type}
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=payload, auth=self.auth)
            if response.status_code == 201:
                return True
            else:
                logger.error(f"Failed to link issues: {response.status_code} - {response.text}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Error linking issues: {e}")
            return False
    
    def get_link_types(self):
        """Get available issue link types"""
        url = f"{self.base_url}/rest/api/3/issueLinkType"
        
        try:
            response = requests.get(url, headers=self.headers, auth=self.auth)
            response.raise_for_status()
            return response.json().get("issueLinkTypes", [])
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching link types: {e}")
            return []


class GeminiService:
    """Service class for Google Gemini API interactions"""
    
    def __init__(self):
        self.api_keys = [settings.GEMINI_API_KEY1, settings.GEMINI_API_KEY2]
        self.current_key_index = 0
        self._configure_api()
    
    def _configure_api(self):
        """Configure Gemini API with current key"""
        genai.configure(api_key=self.api_keys[self.current_key_index])
    
    def _rotate_key(self):
        """Rotate to next API key"""
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        self._configure_api()
    
    def generate_content(self, prompt, retry_count=3):
        """Generate content with automatic key rotation on failure"""
        attempts = 0
        last_error = None
        
        while attempts < len(self.api_keys) * retry_count:
            try:
                # Use flash model for better rate limits
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(prompt)
                return response.text
            except Exception as e:
                last_error = e
                logger.warning(f"Gemini API error with key {self.current_key_index}: {e}")
                
                if '429' in str(e) or 'quota' in str(e).lower():
                    # Wait longer for quota issues
                    time.sleep(5)
                
                self._rotate_key()
                attempts += 1
                
                if attempts % len(self.api_keys) == 0:
                    time.sleep(10)  # Longer wait between full rotations
        
        raise Exception(f"All Gemini API keys failed: {last_error}")
    
    def parse_json_response(self, response_text):
        """Extract and parse JSON from Gemini response"""
        try:
            # Find JSON content in response
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_content = response_text[json_start:json_end]
                return json.loads(json_content)
            else:
                return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON: {e}\nRaw response: {response_text}")
            return None


class AutomationService:
    """Service for AI-powered Jira automation"""
    
    def __init__(self):
        self.jira = JiraService()
        self.gemini = GeminiService()
    
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
        
        response_text = self.gemini.generate_content(prompt)
        return self.gemini.parse_json_response(response_text)
    
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
        
        response_text = self.gemini.generate_content(prompt)
        return self.gemini.parse_json_response(response_text)
    
    def create_automated_workflow(self, requirement):
        """Create complete automated workflow with parent ticket, dev tasks, and test cases"""
        workflow_status = {
            "requirement": requirement,
            "parent_ticket": None,
            "development_tasks": [],
            "test_cases": {},
            "errors": []
        }
        
        try:
            # Step 1: Create parent ticket
            parent_result = self.jira.create_issue(
                f"Main Task: {requirement}",
                f"This is the parent ticket for: {requirement}\n\nSubtasks will be linked to this ticket.",
                "Task"
            )
            workflow_status["parent_ticket"] = parent_result.get("key")
            
            if not workflow_status["parent_ticket"]:
                workflow_status["errors"].append("Failed to create parent ticket")
                return workflow_status
            
            # Step 2: Generate and create development tasks
            logger.info("Generating development tasks...")
            time.sleep(2)  # Rate limiting before AI call
            
            try:
                dev_tasks = self.generate_development_tasks(requirement)
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    workflow_status["errors"].append("AI service quota exceeded. Please try again later.")
                    # Create manual fallback tasks
                    dev_tasks = self._create_fallback_tasks(requirement)
                    workflow_status["errors"].append("Using fallback task generation due to quota limits")
                else:
                    workflow_status["errors"].append(f"Failed to generate development tasks: {str(e)}")
                    return workflow_status
            
            if not dev_tasks:
                workflow_status["errors"].append("No development tasks generated")
                return workflow_status
            
            # Get available link types
            link_types = self.jira.get_link_types()
            link_type = "Relates"
            if link_types:
                available_names = [lt["name"] for lt in link_types]
                for lt in ["Relates", "Relates to", "Dependency"]:
                    if lt in available_names:
                        link_type = lt
                        break
            
            # Create development task tickets
            for i, task in enumerate(dev_tasks):
                description = (f"{task['summary']}\n\n"
                             f"Category: {task['category']}\n"
                             f"Component: {task['component']}\n"
                             f"Parent Task: {workflow_status['parent_ticket']}")
                
                task_result = self.jira.create_issue(task["title"], description, "Task")
                task_key = task_result.get("key")
                
                if task_key:
                    workflow_status["development_tasks"].append({
                        "key": task_key,
                        "title": task["title"],
                        "summary": task["summary"],
                        "category": task["category"]
                    })
                    
                    # Link to parent
                    self.jira.link_issues(workflow_status["parent_ticket"], task_key, link_type)
                    
                    # Step 3: Generate and create test cases for this task (with quota protection)
                    time.sleep(3)  # Rate limiting
                    
                    try:
                        test_cases = self.generate_test_cases(task["summary"])
                    except Exception as e:
                        if "429" in str(e) or "quota" in str(e).lower():
                            workflow_status["errors"].append(f"AI quota exceeded for test cases of task {task_key}")
                            # Create basic test case manually
                            test_cases = self._create_fallback_test_cases(task["title"])
                        else:
                            workflow_status["errors"].append(f"Failed to generate test cases for {task_key}: {str(e)}")
                            continue
                    
                    if test_cases:
                        workflow_status["test_cases"][task_key] = []
                        
                        for tc in test_cases:
                            steps_formatted = "\n".join([f"{i+1}. {step}" for i, step in enumerate(tc.get('steps', ['Execute test']))])
                            tc_description = f"""Test Case: {tc.get('test_name', 'Basic Test')}
            
Description: {tc.get('description', 'Test the functionality')}

Steps:
{steps_formatted}

Expected Result: {tc.get('expected_result', 'Functionality works as expected')}

Priority: {tc.get('priority', 'Medium')}"""
                            
                            tc_summary = f"Test: {tc.get('test_name', 'Basic Test')} [{tc.get('priority', 'Medium')}]"
                            tc_result = self.jira.create_issue(tc_summary, tc_description, "Subtask", task_key)
                            
                            if tc_result.get("key"):
                                workflow_status["test_cases"][task_key].append({
                                    "key": tc_result["key"],
                                    "name": tc.get("test_name", "Basic Test"),
                                    "priority": tc.get("priority", "Medium")
                                })
                            
                            time.sleep(2)  # Rate limiting
            
        except Exception as e:
            workflow_status["errors"].append(str(e))
            logger.error(f"Automation workflow error: {e}")
        
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