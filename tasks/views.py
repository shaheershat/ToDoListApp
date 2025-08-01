from django.shortcuts import render
from django.http import JsonResponse
import json
import os
from datetime import datetime, timezone

def index(request):
    return render(request, 'index.html')

# Email storage location
EMAIL_STORE = os.path.join(os.path.dirname(__file__), 'task', 'emails.json')
TASKS_DIR = os.path.join(os.path.dirname(__file__), 'task') # Defined for clarity

def save_email(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_id = data.get('user_id')
        email = data.get('email')

        if not user_id or not email:
            return JsonResponse({'error': 'Missing user_id or email'}, status=400)

        os.makedirs(os.path.dirname(EMAIL_STORE), exist_ok=True)

        # Load or create email store
        if os.path.exists(EMAIL_STORE):
            with open(EMAIL_STORE, 'r') as f:
                emails = json.load(f)
        else:
            emails = {}

        # Update email for user
        emails[user_id] = email

        with open(EMAIL_STORE, 'w') as f:
            json.dump(emails, f)

        return JsonResponse({'message': 'Email saved successfully'})
    else:
        return JsonResponse({'error': 'Invalid request'}, status=405)


def save_tasks(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_id = data.get('user_id')
        tasks = data.get('tasks')

        if not user_id or tasks is None:
            return JsonResponse({'error': 'Missing user_id or tasks'}, status=400)

        os.makedirs(TASKS_DIR, exist_ok=True) # Use TASKS_DIR defined above

        task_path = os.path.join(TASKS_DIR, f'user_{user_id}.json')

        # Load previous data to preserve `emailed` flag if task hasn't changed its state
        old_tasks_map = {}
        if os.path.exists(task_path):
            with open(task_path, 'r') as f:
                old_tasks = json.load(f)
                old_tasks_map = {t.get('text'): t for t in old_tasks}

        # Process incoming tasks
        for task in tasks:
            # Check for existing task to carry over `emailed` status and `completedAt`
            prev_task = old_tasks_map.get(task.get('text'), {})

            # Update completedAt timestamp for newly completed tasks
            was_done = prev_task.get('done', False)
            is_done = task.get('done', False)

            if is_done and not was_done:
                task['completedAt'] = datetime.utcnow().isoformat() + "Z"
            elif not is_done: # If task becomes undone, clear completedAt
                task['completedAt'] = None
            elif is_done and was_done: # If task was already done, keep its completedAt
                task['completedAt'] = prev_task.get('completedAt')

            # Preserve emailed status if task hasn't been re-scheduled or un-emailed by logic
            if 'emailed' not in task and 'emailed' in prev_task:
                 task['emailed'] = prev_task['emailed']

        with open(task_path, 'w') as f:
            json.dump(tasks, f, indent=2)

        return JsonResponse({'message': 'Tasks saved'})
    else:
        return JsonResponse({'error': 'Invalid request'}, status=405)


def get_tasks_by_date(request):
    """
    Retrieves tasks for a specific date from the user's task file.
    Tasks are filtered based on their remindAt or completedAt date.
    """
    if request.method == 'GET':
        user_id = request.GET.get('user_id')
        date_str = request.GET.get('date') # Format: YYYY-MM-DD

        if not user_id or not date_str:
            return JsonResponse({'error': 'Missing user_id or date'}, status=400)

        task_path = os.path.join(TASKS_DIR, f'user_{user_id}.json')

        if not os.path.exists(task_path):
            return JsonResponse({'tasks': []}) # No tasks file, return empty

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
            # Check if the task was relevant to this specific date
            # A task is relevant if:
            # 1. Its reminder date is on this day OR
            # 2. It was completed on this day OR
            # 3. It's an uncompleted repeating task (relevant for all days until done/deleted)
            # This logic can be adjusted based on how you define "old tasks"
            
            # Convert to date-only for comparison
            remind_date = None
            if task.get('remindAt'):
                try:
                    remind_date = datetime.fromisoformat(task['remindAt'].replace("Z", "+00:00")).date()
                except ValueError:
                    pass # Ignore invalid dates

            completed_date = None
            if task.get('completedAt'):
                try:
                    completed_date = datetime.fromisoformat(task['completedAt'].replace("Z", "+00:00")).date()
                except ValueError:
                    pass # Ignore invalid dates

            # Logic: include if reminder matches OR completed matches OR it's a repeating task that wasn't completed on this day
            # This logic needs refinement based on exactly what "old tasks" means
            # For simplicity, let's include tasks that were DUE or COMPLETED on that day.
            # And also, any tasks that were *pending* on that day (i.e., not completed yet, and due before or on that day).

            # Simplified logic for "tasks for that date":
            # If task's reminder date matches OR completed date matches
            # OR if it's an undone repeating task and its remindAt is before or on target_date
            
            # For "old tasks" modal, we usually want what was 'active' or 'done' on that day.
            # A simpler approach: include tasks whose remindAt matches the date, or completedAt matches the date.
            # For tasks without a specific date (no remindAt or completedAt), or general pending tasks,
            # this view might not be the best place to show them without more complex criteria.

            is_relevant_by_remind = remind_date and (remind_date == target_date)
            is_relevant_by_completion = completed_date and (completed_date == target_date)

            # Option for tasks that were pending on that day:
            # is_pending_on_date = (not task.get('done') and remind_date and remind_date <= target_date)

            if is_relevant_by_remind or is_relevant_by_completion:
                tasks_for_date.append(task)
            # Alternatively, if you want *all* tasks that were active/pending at any point before/on that date:
            # if (not task.get('done') and remind_date and remind_date <= target_date) or is_relevant_by_completion:
            #    tasks_for_date.append(task)

        return JsonResponse({'tasks': tasks_for_date})
    else:
        return JsonResponse({'error': 'Invalid request'}, status=405)