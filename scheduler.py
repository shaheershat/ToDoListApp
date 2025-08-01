# scheduler.py

from apscheduler.schedulers.blocking import BlockingScheduler
from emailer import send_reminder_emails

scheduler = BlockingScheduler()

# Run every minute
scheduler.add_job(send_reminder_emails, 'interval', minutes=1)

print("📅 APScheduler started. Checking for due reminders every 60 seconds.")
scheduler.start()
