from django.shortcuts import render
from django.http import JsonResponse
import json
import os
from datetime import datetime

def index(request):
    """Renders the main To-Do application page."""
    return render(request, 'index.html')

# Define storage directories for emails and user tasks
TASKS_DIR = os.path.join(os.path.dirname(__file__), 'task_data') 
EMAIL_STORE = os.path.join(TASKS_DIR, 'emails.json') 

def save_email(request):
    """Handles saving a user's email for reminders."""
    if request.method == 'POST':
        data = json.loads(request.body)
        user_id = data.get('user_id')
        email = data.get('email')

        if not user_id or not email:
            return JsonResponse({'error': 'Missing user_id or email'}, status=400)

        os.makedirs(TASKS_DIR, exist_ok=True) 

        emails = {}
        if os.path.exists(EMAIL_STORE):
            with open(EMAIL_STORE, 'r') as f:
                try:
                    emails = json.load(f)
                except json.JSONDecodeError:
                    emails = {}

        emails[user_id] = email

        with open(EMAIL_STORE, 'w') as f:
            json.dump(emails, f, indent=2) 

        return JsonResponse({'message': 'Email saved successfully'})
    return JsonResponse({'error': 'Invalid request method'}, status=405)


def save_tasks(request):
    """Handles saving a user's tasks, preserving `emailed` status and updating `completedAt`."""
    if request.method == 'POST':
        data = json.loads(request.body)
        user_id = data.get('user_id')
        tasks = data.get('tasks')

        if not user_id or tasks is None:
            return JsonResponse({'error': 'Missing user_id or tasks'}, status=400)

        os.makedirs(TASKS_DIR, exist_ok=True) 
        task_path = os.path.join(TASKS_DIR, f'user_{user_id}.json')

        old_tasks_map = {}
        if os.path.exists(task_path):
            with open(task_path, 'r') as f:
                try:
                    old_tasks = json.load(f)
                    old_tasks_map = {t.get('text'): t for t in old_tasks if t.get('text')}
                except json.JSONDecodeError:
                    old_tasks_map = {}

        for task in tasks:
            prev_task = old_tasks_map.get(task.get('text'), {})

            was_done = prev_task.get('done', False)
            is_done = task.get('done', False)

            if is_done and not was_done: 
                task['completedAt'] = datetime.utcnow().isoformat() + "Z"
            elif not is_done: 
                task['completedAt'] = None
            elif is_done and was_done: 
                task['completedAt'] = prev_task.get('completedAt')

            if 'emailed' not in task and 'emailed' in prev_task:
                 task['emailed'] = prev_task['emailed']

        with open(task_path, 'w') as f:
            json.dump(tasks, f, indent=2)

        return JsonResponse({'message': 'Tasks saved'})
    return JsonResponse({'error': 'Invalid request method'}, status=405)


def get_tasks_by_date(request):
    """
    Retrieves tasks for a specific date.
    Includes tasks whose reminder date or completion date matches the target date.
    """
    if request.method == 'GET':
        user_id = request.GET.get('user_id')
        date_str = request.GET.get('date') # Expected format: YYYY-MM-DD

        if not user_id or not date_str:
            return JsonResponse({'error': 'Missing user_id or date'}, status=400)

        task_path = os.path.join(TASKS_DIR, f'user_{user_id}.json')

        if not os.path.exists(task_path):
            return JsonResponse({'tasks': []})

        try:
            with open(task_path, 'r') as f:
                all_tasks = json.load(f)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Error reading user task file'}, status=500)

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return JsonResponse({'error': 'Invalid date format'}, status=400)

        tasks_for_date = []
        for task in all_tasks:
            remind_date = None
            if task.get('remindAt'):
                try:
                    remind_date = datetime.fromisoformat(task['remindAt'].replace("Z", "+00:00")).date()
                except ValueError:
                    pass 

            completed_date = None
            if task.get('completedAt'):
                try:
                    completed_date = datetime.fromisoformat(task['completedAt'].replace("Z", "+00:00")).date()
                except ValueError:
                    pass 

            if (remind_date and remind_date == target_date) or \
               (completed_date and completed_date == target_date):
                tasks_for_date.append(task)

        return JsonResponse({'tasks': tasks_for_date})
    return JsonResponse({'error': 'Invalid request method'}, status=405)