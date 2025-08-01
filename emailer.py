import os
import json
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone, timedelta

# Configurations
EMAIL_ADDRESS = 'infoattodoapp@gmail.com'
EMAIL_PASSWORD = 'mrju rzfp ahhn uoea'  # Gmail App Password
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TASKS_DIR = os.path.join(BASE_DIR, 'tasks', 'task')
EMAIL_STORE = os.path.join(TASKS_DIR, 'emails.json')

def get_next_reminder(current_remind_time, repeat_type):
    """Calculates the next reminder time for repeating tasks."""
    if repeat_type == "daily":
        return current_remind_time + timedelta(days=1)
    elif repeat_type == "weekly":
        return current_remind_time + timedelta(weeks=1)
    return None

def send_reminder_emails():
    """
    Checks for due tasks for all users and sends email reminders.
    Only sends for tasks that are not done, due, and not yet emailed for current reminder cycle.
    Updates task 'emailed' status and 'remindAt' for repeating tasks.
    """
    print("Starting send_reminder_emails process...")

    if not os.path.exists(EMAIL_STORE):
        print("No emails.json found. No reminders to send.")
        return

    try:
        with open(EMAIL_STORE, 'r') as f:
            users_emails = json.load(f)
    except json.JSONDecodeError:
        print(f"Error decoding {EMAIL_STORE}. It might be empty or malformed.")
        return # Exit if emails.json is unreadable

    now_utc = datetime.now(timezone.utc)
    print(f"Current UTC time: {now_utc}")

    # Ensure the task directory exists
    os.makedirs(TASKS_DIR, exist_ok=True)

    for user_id, email in users_emails.items():
        print(f"\nProcessing user: {user_id}, Email: {email}")
        task_file = os.path.join(TASKS_DIR, f'user_{user_id}.json')

        if not os.path.exists(task_file):
            print(f"No task file found for user {user_id} at {task_file}.")
            continue

        try:
            with open(task_file, 'r') as f:
                task_data = json.load(f)
        except json.JSONDecodeError:
            print(f"Error decoding task file for user {user_id}. Skipping.")
            continue

        tasks_to_remind_in_email = [] # Tasks that will be listed in the email for this user
        tasks_to_update_after_email = [] # Tasks whose 'emailed' or 'remindAt' status needs saving

        for task in task_data:
            # Create a copy to work with for potential updates without modifying original in loop
            processed_task = task.copy()
            remind_at_str = processed_task.get('remindAt')
            emailed_status = processed_task.get('emailed', False)
            is_done = processed_task.get('done', False)
            repeat_type = processed_task.get('repeat')

            # --- CRUCIAL CHECKS ---
            # 1. Skip if already marked as done
            if is_done:
                print(f"  Skipping task '{processed_task.get('text', 'UNKNOWN')}' - marked as done.")
                tasks_to_update_after_email.append(processed_task) # Keep completed tasks in the list
                continue
            
            # 2. Skip if no reminder time set
            if not remind_at_str:
                print(f"  Skipping task '{processed_task.get('text', 'UNKNOWN')}' - no reminder time set.")
                tasks_to_update_after_email.append(processed_task)
                continue

            try:
                # Ensure timezone-aware parsing
                remind_at = datetime.fromisoformat(remind_at_str.replace("Z", "+00:00"))
            except ValueError:
                print(f"  Invalid date format for task '{processed_task.get('text', 'UNKNOWN')}' for user {user_id}. Skipping reminder.")
                tasks_to_update_after_email.append(processed_task)
                continue

            print(f"  Processing: '{processed_task['text']}', Remind At: {remind_at}, Emailed: {emailed_status}")

            # 3. Check if due AND not yet emailed for this reminder period
            if remind_at <= now_utc and not emailed_status:
                tasks_to_remind_in_email.append(processed_task)
                print(f"  -> DUE for reminder: '{processed_task['text']}'")

                # Prepare for next reminder or mark as permanently emailed
                if repeat_type in ["daily", "weekly"]:
                    next_remind_time = get_next_reminder(remind_at, repeat_type)
                    if next_remind_time:
                        processed_task['remindAt'] = next_remind_time.isoformat().replace("+00:00", "Z")
                        processed_task['emailed'] = False # Reset for the next occurrence
                        print(f"  -> Repeating task, next reminder set to: {processed_task['remindAt']}")
                    else:
                        # Fallback: if next_remind_time couldn't be calculated for a repeating task
                        processed_task['emailed'] = True
                        print(f"  -> Repeating task, but next time could not be calculated. Marking as emailed.")
                else:
                    processed_task['emailed'] = True # Mark as emailed for one-time tasks
                    print(f"  -> One-time task, marking as emailed.")
            
            tasks_to_update_after_email.append(processed_task) # Add the (potentially updated) task

        if not tasks_to_remind_in_email:
            print(f"No new due reminders for user {user_id}.")
            # Even if no email sent, save any updates (e.g., if a task was marked done)
            if tasks_to_update_after_email != task_data: # Only write if there were actual changes
                 with open(task_file, 'w') as f:
                    json.dump(tasks_to_update_after_email, f, indent=2)
                 print(f"No email sent, but task data updated for user {user_id}.")
            continue

        # Prepare email content for tasks that are due and will be reminded
        # Include all pending and completed tasks in the summary, regardless of reminder status
        pending_summary_tasks = [t['text'] for t in tasks_to_update_after_email if not t.get('done') and not t.get('emailed')]
        completed_summary_tasks = [t['text'] for t in tasks_to_update_after_email if t.get('done')]
        due_texts_for_email = [t['text'] for t in tasks_to_remind_in_email]

        body = f"""Hello!

⏰ You have reminders for these tasks:
{chr(10).join(due_texts_for_email) if due_texts_for_email else 'None'}

📌 Your current pending tasks:
{chr(10).join(pending_summary_tasks) if pending_summary_tasks else 'None'}

✅ Your completed tasks:
{chr(10).join(completed_summary_tasks) if completed_summary_tasks else 'None'}

Have a productive day!
"""

        msg = EmailMessage()
        msg['Subject'] = '📝 Your To-Do List Reminder'
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = email
        msg.set_content(body)

        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                smtp.send_message(msg)
            print(f"✅ Reminder email sent to {email} for {len(due_texts_for_email)} tasks.")

            # Save the updated task data to the file only after successful email sending
            with open(task_file, 'w') as f:
                json.dump(tasks_to_update_after_email, f, indent=2)
            print(f"Updated task data saved for user {user_id} after email.")

        except Exception as e:
            print(f"❌ Error sending email to {email}: {e}. Task data NOT updated to avoid losing state.")

    print("\nFinished send_reminder_emails process.")

# Example usage (for testing, you'd typically run this via a scheduler like cron)
if __name__ == "__main__":
    # Ensure the task directory exists for testing
    if not os.path.exists(TASKS_DIR):
        os.makedirs(TASKS_DIR)

    dummy_user_id = "test_user_123"
    dummy_email = "your_email@example.com" # <--- IMPORTANT: Change this to your actual email for testing!

    # Create dummy emails.json
    dummy_emails_data = {dummy_user_id: dummy_email}
    with open(EMAIL_STORE, 'w') as f:
        json.dump(dummy_emails_data, f, indent=2)

    # Create dummy user_task.json for testing various scenarios
    dummy_tasks_data = [
        {
            "text": "One-time task due now",
            "done": False,
            "remindAt": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            "emailed": False,
            "repeat": ""
        },
        {
            "text": "Daily repeating task due now",
            "done": False,
            "remindAt": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z"),
            "emailed": False,
            "repeat": "daily"
        },
        {
            "text": "Weekly repeating task due now",
            "done": False,
            "remindAt": (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
            "emailed": False,
            "repeat": "weekly"
        },
        {
            "text": "Already emailed one-time task",
            "done": False,
            "remindAt": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
            "emailed": True, # Should NOT send email
            "repeat": ""
        },
        {
            "text": "Future task (not due yet)",
            "done": False,
            "remindAt": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            "emailed": False, # Should NOT send email
            "repeat": ""
        },
        {
            "text": "Completed task (should not email)",
            "done": True,
            "remindAt": (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat().replace("+00:00", "Z"),
            "emailed": False, # Even if emailed: false, done: true means no email
            "repeat": "daily",
            "completedAt": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        },
        {
            "text": "Task without reminder",
            "done": False,
            "remindAt": None, # Should not send email
            "emailed": False,
            "repeat": ""
        }
    ]
    with open(os.path.join(TASKS_DIR, f'user_{dummy_user_id}.json'), 'w') as f:
        json.dump(dummy_tasks_data, f, indent=2)

    send_reminder_emails()