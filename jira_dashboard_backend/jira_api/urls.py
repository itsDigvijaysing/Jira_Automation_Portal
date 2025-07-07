# jira_api/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Issue viewing endpoints
    path('issues/', views.fetch_issues, name='fetch_issues'),
    path('issues/<str:issue_key>/', views.fetch_issue_details, name='fetch_issue_details'),
    
    # Automation endpoints
    path('automation/workflow/', views.create_automation_workflow, name='create_automation_workflow'),
    path('automation/generate-tasks/', views.generate_dev_tasks, name='generate_dev_tasks'),
    path('automation/generate-tests/', views.generate_test_cases, name='generate_test_cases'),
    path('automation/status/', views.get_workflow_status, name='get_workflow_status'),
]