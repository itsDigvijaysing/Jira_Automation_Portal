# jira_api/views.py
from functools import lru_cache
import logging
import re

from django.core.exceptions import ImproperlyConfigured
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .services import JiraService, AutomationService, JiraAPIError

logger = logging.getLogger(__name__)

# Jira issue keys look like "SCRUM-12". Checked before the key goes into a Jira URL.
ISSUE_KEY_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*-[0-9]+$')
MAX_TEXT_LENGTH = 2000  # matches the textarea limit in the frontend


def _error_response(error):
    """Map an exception to a JSON error response with a fitting status code."""
    if isinstance(error, JiraAPIError):
        # Pass 404 through (unknown issue); anything else is an upstream failure.
        code = status.HTTP_404_NOT_FOUND if error.status_code == 404 else status.HTTP_502_BAD_GATEWAY
    else:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR
    return Response({"error": str(error)}, status=code)


def _read_text(request, field, label):
    """Return (text, None) for a valid string field, or (None, error Response)."""
    data = request.data if isinstance(request.data, dict) else {}
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        return None, Response({"error": f"{label} is required"}, status=status.HTTP_400_BAD_REQUEST)
    value = value.strip()
    if len(value) > MAX_TEXT_LENGTH:
        return None, Response(
            {"error": f"{label} must be at most {MAX_TEXT_LENGTH} characters"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return value, None


# Lazily build services so a missing/invalid env var (e.g. Gemini keys) surfaces
# as a request-time error instead of crashing the app at import time.
@lru_cache(maxsize=1)
def get_jira_service():
    return JiraService()


@lru_cache(maxsize=1)
def get_automation_service():
    return AutomationService()


@api_view(['GET'])
def fetch_issues(request):
    """Fetch all Jira issues"""
    try:
        result = get_jira_service().fetch_issues()
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error in fetch_issues: {e}")
        return _error_response(e)


@api_view(['GET'])
def fetch_issue_details(request, issue_key):
    """Fetch details for a specific issue"""
    if not ISSUE_KEY_RE.match(issue_key):
        return Response({"error": "Invalid issue key"}, status=status.HTTP_400_BAD_REQUEST)
    try:
        result = get_jira_service().fetch_issue_details(issue_key)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error in fetch_issue_details: {e}")
        return _error_response(e)


@api_view(['POST'])
def create_automation_workflow(request):
    """Create automated workflow from requirement"""
    try:
        requirement, invalid = _read_text(request, 'requirement', 'Requirement')
        if invalid:
            return invalid
        
        # Run the automation workflow
        result = get_automation_service().create_automated_workflow(requirement)
        
        # Check if there were any errors
        if result.get("errors"):
            return Response(result, status=status.HTTP_207_MULTI_STATUS)
        
        return Response(result, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error in create_automation_workflow: {e}")
        return _error_response(e)


@api_view(['POST'])
def generate_dev_tasks(request):
    """Generate development tasks for a requirement"""
    try:
        requirement, invalid = _read_text(request, 'requirement', 'Requirement')
        if invalid:
            return invalid
        
        tasks = get_automation_service().generate_development_tasks(requirement)
        if not tasks:
            return Response(
                {"error": "The AI returned no usable tasks"},
                status=status.HTTP_502_BAD_GATEWAY
            )
        
        return Response({"tasks": tasks}, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error in generate_dev_tasks: {e}")
        return _error_response(e)


@api_view(['POST'])
def generate_test_cases(request):
    """Generate test cases for a task"""
    try:
        task_description, invalid = _read_text(request, 'task_description', 'Task description')
        if invalid:
            return invalid
        
        test_cases = get_automation_service().generate_test_cases(task_description)
        if not test_cases:
            return Response(
                {"error": "The AI returned no usable test cases"},
                status=status.HTTP_502_BAD_GATEWAY
            )
        
        return Response({"test_cases": test_cases}, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error in generate_test_cases: {e}")
        return _error_response(e)


@api_view(['GET'])
def get_workflow_status(request):
    """Get status of ongoing workflows (placeholder for future websocket implementation)"""
    return Response({
        "message": "Workflow status endpoint - to be implemented with WebSockets",
        "status": "ready"
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
def test_jira_connection(request):
    """Test Jira API connection and get basic info"""
    try:
        jira_service = get_jira_service()
    except ImproperlyConfigured as e:
        return Response({"connection": "failed", "error": str(e)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    try:
        user_info = jira_service.get_myself()
        projects = jira_service.get_projects(limit=10)

        return Response({
            "connection": "success",
            "user": user_info.get('displayName', 'Unknown'),
            "email": user_info.get('emailAddress', 'Unknown'),
            "jira_url": jira_service.base_url,
            "configured_project": jira_service.project_key,
            "available_projects": [{"key": p.get("key"), "name": p.get("name")} for p in projects]
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error testing Jira connection: {e}")
        return Response({
            "connection": "failed",
            "error": str(e),
            "jira_url": jira_service.base_url,
            "configured_project": jira_service.project_key,
        }, status=status.HTTP_502_BAD_GATEWAY if isinstance(e, JiraAPIError)
           else status.HTTP_500_INTERNAL_SERVER_ERROR)
