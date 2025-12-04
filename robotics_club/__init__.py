"""
Django App Initialization

Loads Celery on startup for async task processing.
"""

from .celery import app as celery_app

__all__ = ('celery_app',)
