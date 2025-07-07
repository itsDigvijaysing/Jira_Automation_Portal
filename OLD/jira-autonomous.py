import requests
from requests.auth import HTTPBasicAuth
import json
import time
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

# === Jira Credentials & Constants ===
EMAIL = os.getenv("JIRA_EMAIL")
API_TOKEN = os.getenv("JIRA_API_TOKEN")
# https://id.atlassian.com/manage-profile/security/api-tokens
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
PROJECT_KEY = "CPG"

auth = HTTPBasicAuth(EMAIL, API_TOKEN)
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
} 

# === Gemini API Configuration ===
gemini_keys = [os.getenv('GEMINI_API_KEY1'), os.getenv('GEMINI_API_KEY2')]
current_gemini_index = 0

def get_gemini_instance():
    """
    Initialize the Gemini API using the current key.
    """
    global current_gemini_index
    api_key = gemini_keys[current_gemini_index]
    genai.configure(api_key=api_key)
    # Create a generative model with the specific model name
    return genai.GenerativeModel('gemini-1.5-pro-latest')

def generate_content_with_fallback(prompt):
    """
    Generate content using Gemini API with key fallback and delay logic.
    """
    global current_gemini_index
    initial_index = current_gemini_index  # Remember starting key index
    attempts = 0

    while attempts < len(gemini_keys):
        try:
            model = get_gemini_instance()
            # Use generate_content instead of generate_text
            response = model.generate_content(prompt)
            
            # Extract text from the response
            return response.text
        
        except Exception as e:
            print(f"Gemini key {gemini_keys[current_gemini_index]} failed: {e}")
            # If the error message indicates rate limit or quota issues, wait before trying the next key
            if '429' in str(e) or 'quota' in str(e):
                time.sleep(1)  # Wait 1 second
            
            # Move to the next key
            current_gemini_index = (current_gemini_index + 1) % len(gemini_keys)
            attempts += 1

            # If we've cycled through all keys, wait a bit longer before retrying
            if current_gemini_index == initial_index:
                time.sleep(2)
    
    raise Exception("All Gemini API keys failed after multiple attempts")

# === POST: Create a new Jira ticket ===
def create_jira_ticket(summary: str, description: str):
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": PROJECT_KEY},
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
            "issuetype": {"name": "Task"},
            "assignee": {"id": "712020:f1dccbef-1286-406d-979d-e8adfe4cb987"}  # Replace with your actual accountId if needed
        }
    }
    response = requests.post(url, headers=headers, json=payload, auth=auth)
    if response.status_code == 201:
        issue_key = response.json()["key"]
        print(f"Created Jira ticket: {issue_key}")
        return issue_key
    else:
        print("❌ Failed to create ticket:")
        print(response.status_code, response.text)
        return None

# === POST: Create a new Jira subtask ===
def create_jira_subtask(parent_key: str, summary: str, description: str):
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": PROJECT_KEY},
            "parent": {"key": parent_key},
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
            "issuetype": {"name": "Subtask"},
            "assignee": {"id": "712020:f1dccbef-1286-406d-979d-e8adfe4cb987"}  # Replace with your actual accountId if needed
        }
    }
    response = requests.post(url, headers=headers, json=payload, auth=auth)
    if response.status_code == 201:
        issue_key = response.json()["key"]
        print(f"Created Jira subtask: {issue_key} under parent {parent_key}")
        return issue_key
    else:
        print(f"Failed to create subtask under {parent_key}:")
        print(response.status_code, response.text)
        return None

# === GET: Fetch tickets (excluding sample tickets) ===
def fetch_visible_tickets():
    url = f"{JIRA_BASE_URL}/rest/api/3/search"
    params = {
        "jql": f"project={PROJECT_KEY} AND key NOT IN (CPG-1, CPG-2)",
        "maxResults": 50,
        "fields": "summary,status,assignee"
    }
    response = requests.get(url, headers=headers, params=params, auth=auth)
    if response.status_code == 200:
        issues = response.json().get("issues", [])
        print(f"\nTotal visible tickets: {len(issues)}\n")
        for issue in issues:
            key = issue["key"]
            summary = issue["fields"]["summary"]
            status = issue["fields"]["status"]["name"]
            assignee = issue["fields"]["assignee"]["displayName"] if issue["fields"]["assignee"] else "Unassigned"
            print(f"{key}: {summary} [Status: {status}] (Assigned to: {assignee})")
        return issues
    else:
        print("❌ Failed to fetch tickets:")
        print(response.status_code, response.text)
        return []

# === Function: Generate subtasks using Gemini API ===
def generate_development_tasks(requirement):
    """
    Generate structured development tasks for a given requirement.
    Returns JSON array of task objects.
    """
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
    
    response_text = generate_content_with_fallback(prompt)
    
    # Extract JSON from the response
    try:
        # Find and extract JSON content (in case there's surrounding text)
        json_start = response_text.find('[')
        json_end = response_text.rfind(']') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_content = response_text[json_start:json_end]
            return json.loads(json_content)
        else:
            # If we can't find JSON brackets, try parsing the whole response
            return json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        print(f"Raw response: {response_text}")
        return None

# === Function: Get available link types ===
def get_link_types():
    """Get all available issue link types in Jira"""
    url = f"{JIRA_BASE_URL}/rest/api/3/issueLinkType"
    response = requests.get(url, headers=headers, auth=auth)
    
    if response.status_code == 200:
        link_types = response.json().get("issueLinkTypes", [])
        print("\n🔗 Available link types:")
        for lt in link_types:
            print(f"  - {lt['name']} (inward: {lt['inward']}, outward: {lt['outward']})")
        return link_types
    else:
        print("Failed to fetch link types:")
        print(response.status_code, response.text)
        return []

# === Function: Link two JIRA issues with better error handling ===
def link_issues(outward_issue, inward_issue, link_type="Relates"):
    """Link two JIRA issues with the specified relationship type"""
    url = f"{JIRA_BASE_URL}/rest/api/3/issueLink"
    
    payload = {
        "outwardIssue": {"key": outward_issue},
        "inwardIssue": {"key": inward_issue},
        "type": {"name": link_type}
    }
    
    print(f"Sending link request: {json.dumps(payload)}")
    
    response = requests.post(url, headers=headers, json=payload, auth=auth)
    
    if response.status_code == 201:
        print(f"Successfully linked {outward_issue} and {inward_issue} with type '{link_type}'")
        return True
    else:
        print(f"Failed to link issues {outward_issue} and {inward_issue}:")
        print(f"   Status code: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

# === Function: Create JIRA tickets for subtasks and link to parent ===
def create_linked_subtasks(parent_key, subtasks):
    """Create JIRA tickets for each subtask and link to parent ticket"""
    created_issues = []
    task_data_map = {}  # Map to store task key -> task data
    
    # First, let's get available link types
    link_types = get_link_types()
    
    # Try to find a suitable link type
    standard_link_types = ["Relates", "Relates to", "Dependency", "Parent/Child", "Blocks"]
    available_link_names = [lt["name"] for lt in link_types]
    
    # Find the first matching link type
    link_type_to_use = None
    for lt in standard_link_types:
        if lt in available_link_names:
            link_type_to_use = lt
            break
    
    if not link_type_to_use and link_types:
        # If none of our standard types match, use the first available one
        link_type_to_use = link_types[0]["name"]
    
    if not link_type_to_use:
        print("No link types available, will create tickets without linking")
    else:
        print(f"Will use link type: {link_type_to_use}")
    
    for idx, task in enumerate(subtasks):
        # Prepare a detailed description
        description = (f"{task['summary']}\n\n"
                      f"Category: {task['category']}\n"
                      f"Component: {task['component']}\n"
                      f"Parent Task: {parent_key}")
        
        # Create the subtask
        issue_key = create_jira_ticket(task["title"], description)
        
        if issue_key:
            created_issues.append(issue_key)
            # Store task data mapped to this issue key
            task_data_map[issue_key] = task
            
            # Link to parent ticket if we have a link type
            if link_type_to_use:
                print(f"Attempting to link {issue_key} to {parent_key}...")
                time.sleep(1)  # Add a small delay to avoid rate limiting
                link_success = link_issues(parent_key, issue_key, link_type_to_use)
                
                # If the first attempt fails, try with another common link type
                if not link_success and len(link_types) > 1:
                    print("First link attempt failed, trying with another link type...")
                    time.sleep(1)  # Add a small delay
                    alt_link_type = link_types[1]["name"]
                    link_success = link_issues(parent_key, issue_key, alt_link_type)
    
    return created_issues, task_data_map

# === Function: Generate and create test cases for a task description and task key ===
def generate_and_create_test_cases(task_description, task_key):
    """
    Takes a task description and task key, generates test cases using Gemini API, 
    creates them as subtasks, and returns the created subtask keys.
    
    Args:
        task_description (str): Description of the task to generate test cases for
        task_key (str): Jira key of the parent task
        
    Returns:
        list: List of created subtask keys
    """
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
    
    print(f"\n🧪 Generating test cases for task {task_key}...")
    response_text = generate_content_with_fallback(prompt)
    
    created_subtasks = []
    
    # Extract JSON from the response
    try:
        # Find and extract JSON content (in case there's surrounding text)
        json_start = response_text.find('[')
        json_end = response_text.rfind(']') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_content = response_text[json_start:json_end]
            test_cases = json.loads(json_content)
        else:
            # If we can't find JSON brackets, try parsing the whole response
            test_cases = json.loads(response_text)
            
        # Print the test cases
        print(f"\nGenerated {len(test_cases)} test cases for task {task_key}:")
        for tc in test_cases:
            print(f"\n--- {tc['test_id']}: {tc['test_name']} (Priority: {tc['priority']}) ---")
            print(f"Description: {tc['description']}")
            print("Steps:")
            for i, step in enumerate(tc['steps'], 1):
                print(f"  {i}. {step}")
            print(f"Expected Result: {tc['expected_result']}")
            
            # Create a detailed description for the subtask
            steps_formatted = "\n".join([f"{i+1}. {step}" for i, step in enumerate(tc['steps'])])
            subtask_description = f"""Test Case: {tc['test_name']}
            
Description: {tc['description']}

Steps:
{steps_formatted}

Expected Result: {tc['expected_result']}

Priority: {tc['priority']}
"""
            
            # Create a subtask for this test case
            subtask_summary = f"Test: {tc['test_name']} [{tc['priority']}]"
            subtask_key = create_jira_subtask(task_key, subtask_summary, subtask_description)
            
            if subtask_key:
                created_subtasks.append(subtask_key)
                print(f"Created test case subtask: {subtask_key}")
                time.sleep(1)  # Add a small delay to avoid rate limiting
            
        return created_subtasks
        
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        print(f"Raw response: {response_text}")
        return []

# === Main Process ===
if __name__ == "__main__":
    # Step 1: Get a high-level requirement from the user
    requirement = input("Enter the main task/requirement: ")
    
    # Step 2: Create a parent ticket for the main requirement
    print("\nCreating parent ticket for the main requirement...")
    parent_key = create_jira_ticket(
        f"Main Task: {requirement}", 
        f"This is the parent ticket for: {requirement}\n\nSubtasks will be linked to this ticket."
    )
    
    if not parent_key:
        print("Failed to create parent ticket. Exiting.")
        exit(1)
    
    # Step 3: Generate subtasks using Gemini API
    print("\nGenerating subtasks using Gemini API...")
    subtasks = generate_development_tasks(requirement)
    
    created_task_keys = []
    task_data_map = {}  # To store mapping of task keys to their data
    
    if subtasks:
        print("\nGemini returned the following subtasks:")
        for idx, task in enumerate(subtasks, start=1):
            print(f"{idx}. {task['title']}: {task['summary']}")
        
        # Step 4: Create JIRA tickets for each subtask and link to parent
        print("\nCreating Jira tickets for each subtask and linking them to parent...")
        created_task_keys, task_data_map = create_linked_subtasks(parent_key, subtasks)
    else:
        print("No subtasks generated by Gemini API.")
    
    # Step 5: For each created task, generate test cases and create them as subtasks
    if created_task_keys:
        print(f"\n== Creating Test Case Subtasks for {len(created_task_keys)} tasks ==")
        
        for task_key in created_task_keys:
            # Get the task data from our map
            task_data = task_data_map.get(task_key)
            
            if task_data:
                # Generate test cases and create them as subtasks for this specific task
                print(f"\nProcessing task {task_key}: {task_data['title']}")
                test_case_subtasks = generate_and_create_test_cases(
                    task_data['summary'], 
                    task_key
                )
                print(f"\nCreated {len(test_case_subtasks)} test case subtasks for {task_key}")
                time.sleep(2)  # Add a delay between task processing
            else:
                print(f"Could not find task data for {task_key}, skipping test case generation")
    
    # Step 6: Fetch and display all tickets after creation
    fetch_visible_tickets()