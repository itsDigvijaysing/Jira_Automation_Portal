# views.py
import json
import requests
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

def get_jira_headers():
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

def get_jira_auth():
    return (settings.JIRA_EMAIL, settings.JIRA_API_TOKEN)

@csrf_exempt
def get_issues(request):
    """
    Fetch issues from Jira
    """
    try:
        # Default JQL query to get all issues from SCRUM project
        jql_query = "project = SCRUM ORDER BY created DESC"
        
        # You can allow frontend to pass custom JQL
        if request.method == "POST":
            data = json.loads(request.body)
            if "jql" in data:
                jql_query = data["jql"]
                
        # API endpoint for searching issues
        endpoint = f"{settings.JIRA_URL}/rest/api/3/search"
        
        # Parameters for the search
        params = {
            "jql": jql_query,
            "maxResults": 50,  # Adjust as needed
            "fields": "summary,description,status,assignee,priority,issuetype,created,updated"
        }
        
        response = requests.get(
            endpoint, 
            headers=get_jira_headers(), 
            auth=get_jira_auth(),
            params=params
        )
        
        if response.status_code == 200:
            return JsonResponse(response.json())
        else:
            return JsonResponse({"error": response.text}, status=response.status_code)
            
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

@csrf_exempt
def get_issue_details(request, issue_key):
    """
    Fetch details for a specific issue
    """
    try:
        endpoint = f"{settings.JIRA_URL}/rest/api/3/issue/{issue_key}"
        
        response = requests.get(
            endpoint,
            headers=get_jira_headers(),
            auth=get_jira_auth()
        )
        
        if response.status_code == 200:
            return JsonResponse(response.json())
        else:
            return JsonResponse({"error": response.text}, status=response.status_code)
            
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)