"""
Celery Configuration for Robotics Club Backend

Production-ready async task processing for:
- Heavy FCM push notification sends
- Scheduled cleanup tasks
- Background processing
"""

import os
from celery import Celery

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'robotics_club.settings')

# Create Celery app
app = Celery('robotics_club')

# Load config from Django settings with 'CELERY_' prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Test task for Celery debugging"""
    print(f'Request: {self.request!r}')
