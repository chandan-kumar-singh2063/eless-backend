"""
Celery Tasks for Async Processing

Heavy operations that should run in the background:
- FCM push notification batching (100+ users)
- Scheduled token cleanup
- Analytics aggregation
"""

from celery import shared_task
from celery.utils.log import get_task_logger
import logging

logger = get_task_logger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name='authentication.send_push_notification_async'
)
def send_push_notification_async(self, title, body, user_ids=None, data=None):
    """
    Async task for sending push notifications
    
    Args:
        title: Notification title
        body: Notification message
        user_ids: List of user IDs (None = broadcast to all)
        data: Additional data payload (dict)
    
    Returns:
        dict: {
            'success': bool,
            'sent_count': int,
            'failed_count': int,
            'details': dict
        }
    """
    try:
        # Import inside task to avoid circular imports
        from authentication.push_notifications import (
            send_to_all_users,
            send_to_multiple_users
        )
        
        logger.info(
            f"[Celery] Sending push notification: title='{title}', "
            f"user_ids={len(user_ids) if user_ids else 'ALL'}"
        )
        
        if user_ids:
            # Send to specific users
            result = send_to_multiple_users(
                user_ids=user_ids,
                title=title,
                body=body,
                data=data
            )
        else:
            # Broadcast to all users
            result = send_to_all_users(
                title=title,
                body=body,
                data=data
            )
        
        logger.info(
            f"[Celery] Push notification sent: "
            f"success={result['sent_count']}, failed={result['failed_count']}"
        )
        
        return result
    
    except Exception as exc:
        logger.error(f"[Celery] Push notification failed: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@shared_task(
    bind=True,
    max_retries=2,
    name='authentication.cleanup_invalid_tokens_async'
)
def cleanup_invalid_tokens_async(self):
    """
    Scheduled task to clean up invalid FCM tokens
    
    Should be run periodically (e.g., daily at 3 AM)
    
    Returns:
        dict: Cleanup statistics
    """
    try:
        from authentication.firebase_client_v2 import get_firebase_client
        
        logger.info("[Celery] Starting scheduled token cleanup...")
        
        client = get_firebase_client()
        # This will be called when send_multicast detects invalid tokens
        # For now, just log that the task ran
        
        logger.info("[Celery] Token cleanup completed")
        
        return {
            'success': True,
            'message': 'Cleanup task ran successfully'
        }
    
    except Exception as exc:
        logger.error(f"[Celery] Token cleanup failed: {str(exc)}")
        raise self.retry(exc=exc)


@shared_task(name='authentication.send_event_notification_async')
def send_event_notification_async(event_id, notification_type='new_event'):
    """
    Async task for event-related notifications
    
    Args:
        event_id: ID of the event
        notification_type: 'new_event', 'event_update', 'event_reminder'
    
    Returns:
        dict: Notification result
    """
    try:
        from events.models import Event
        from authentication.push_notifications import send_to_all_users
        
        event = Event.objects.get(id=event_id)
        
        title_map = {
            'new_event': f"🎯 New Event: {event.title}",
            'event_update': f"📢 Event Updated: {event.title}",
            'event_reminder': f"⏰ Reminder: {event.title}"
        }
        
        title = title_map.get(notification_type, f"Event: {event.title}")
        body = event.description[:100] + "..." if len(event.description) > 100 else event.description
        
        result = send_to_all_users(
            title=title,
            body=body,
            data={
                'event_id': str(event.id),
                'type': notification_type,
                'action': 'open_event_details'
            }
        )
        
        logger.info(
            f"[Celery] Event notification sent for event_id={event_id}, "
            f"type={notification_type}, sent={result['sent_count']}"
        )
        
        return result
    
    except Exception as exc:
        logger.error(f"[Celery] Event notification failed: {str(exc)}")
        return {
            'success': False,
            'error': str(exc)
        }
