# jira_api/views.py
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
import logging

from .services import JiraService, AutomationService

logger = logging.getLogger(__name__)

# Initialize services
jira_service = JiraService()
automation_service = AutomationService()


@api_view(['GET'])
def fetch_issues(request):
    """Fetch all Jira issues"""
    try:
        result = jira_service.fetch_issues()
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error in fetch_issues: {e}")
        return Response(
            {"error": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def fetch_issue_details(request, issue_key):
    """Fetch details for a specific issue"""
    try:
        result = jira_service.fetch_issue_details(issue_key)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error in fetch_issue_details: {e}")
        return Response(
            {"error": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@csrf_exempt
def create_automation_workflow(request):
    """Create automated workflow from requirement"""
    try:
        requirement = request.data.get('requirement')
        if not requirement:
            return Response(
                {"error": "Requirement is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Run the automation workflow
        result = automation_service.create_automated_workflow(requirement)
        
        # Check if there were any errors
        if result.get("errors"):
            return Response(result, status=status.HTTP_207_MULTI_STATUS)
        
        return Response(result, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error in create_automation_workflow: {e}")
        return Response(
            {"error": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@csrf_exempt
def generate_dev_tasks(request):
    """Generate development tasks for a requirement"""
    try:
        requirement = request.data.get('requirement')
        if not requirement:
            return Response(
                {"error": "Requirement is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        tasks = automation_service.generate_development_tasks(requirement)
        if not tasks:
            return Response(
                {"error": "Failed to generate tasks"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response({"tasks": tasks}, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error in generate_dev_tasks: {e}")
        return Response(
            {"error": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@csrf_exempt
def generate_test_cases(request):
    """Generate test cases for a task"""
    try:
        task_description = request.data.get('task_description')
        if not task_description:
            return Response(
                {"error": "Task description is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        test_cases = automation_service.generate_test_cases(task_description)
        if not test_cases:
            return Response(
                {"error": "Failed to generate test cases"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        return Response({"test_cases": test_cases}, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error in generate_test_cases: {e}")
        return Response(
            {"error": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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
        # Test basic connection by getting user info
        url = f"{jira_service.base_url}/rest/api/3/myself"
        import requests
        response = requests.get(url, headers=jira_service.headers, auth=jira_service.auth)
        response.raise_for_status()
        user_info = response.json()
        
        # Get available projects
        projects_url = f"{jira_service.base_url}/rest/api/3/project"
        projects_response = requests.get(projects_url, headers=jira_service.headers, auth=jira_service.auth)
        projects_response.raise_for_status()
        projects = projects_response.json()
        
        return Response({
            "connection": "success",
            "user": user_info.get('displayName', 'Unknown'),
            "email": user_info.get('emailAddress', 'Unknown'),
            "jira_url": jira_service.base_url,
            "configured_project": jira_service.project_key,
            "available_projects": [{"key": p["key"], "name": p["name"]} for p in projects[:10]]
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Error testing Jira connection: {e}")
        return Response({
            "connection": "failed",
            "error": str(e),
            "jira_url": jira_service.base_url,
            "configured_project": jira_service.project_key,
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)