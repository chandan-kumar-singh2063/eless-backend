"""
Push Notification Helper Functions for Firebase Cloud Messaging

Provides easy-to-use functions for sending push notifications:
- send_to_device(fcm_token, title, body, data)
- send_to_user(user, title, body, data)
- send_to_all(title, body, data)

Uses firebase_client_v2 for production-ready FCM with retry logic.
"""

import logging
from typing import Dict, List, Optional, Tuple
from .models import Member, DeviceToken
from .firebase_client_v2 import send_push_notification_with_retry

logger = logging.getLogger(__name__)


def send_to_device(
    fcm_token: str,
    title: str,
    body: str,
    data: Optional[Dict] = None
) -> Tuple[bool, str]:
    """
    Send push notification to a single device.
    
    Args:
        fcm_token: FCM token of the target device
        title: Notification title
        body: Notification body
        data: Optional data payload (dict)
    
    Returns:
        Tuple of (success: bool, message: str)
    
    Example:
        success, msg = send_to_device(
            fcm_token="eXAMPLE_TOKEN",
            title="New Event",
            body="Robotics Workshop Tomorrow",
            data={"event_id": "123"}
        )
    """
    if not fcm_token or not fcm_token.strip():
        return False, "fcm_token cannot be empty"
    
    if not title or not title.strip():
        return False, "title cannot be empty"
    
    if not body or not body.strip():
        return False, "body cannot be empty"
    
    try:
        result = send_push_notification_with_retry(
            fcm_tokens=[fcm_token.strip()],
            title=title.strip(),
            body=body.strip(),
            data_payload=data or {}
        )
        
        if result.get('success', 0) > 0:
            return True, f"Notification sent successfully"
        else:
            error_msg = result.get('errors', ['Unknown error'])[0] if result.get('errors') else 'Unknown error'
            return False, f"Failed to send notification: {error_msg}"
    
    except Exception as e:
        logger.error(f"Error sending notification to device: {str(e)}")
        return False, f"Error: {str(e)}"


def send_to_user(
    user: Member,
    title: str,
    body: str,
    data: Optional[Dict] = None
) -> Tuple[int, int, str]:
    """
    Send push notification to all devices of a specific user.
    
    Args:
        user: Member instance
        title: Notification title
        body: Notification body
        data: Optional data payload (dict)
    
    Returns:
        Tuple of (success_count: int, total_count: int, message: str)
    
    Example:
        success, total, msg = send_to_user(
            user=member,
            title="Welcome Back!",
            body="You have 3 new notifications",
            data={"notification_count": 3}
        )
    """
    if not title or not title.strip():
        return 0, 0, "title cannot be empty"
    
    if not body or not body.strip():
        return 0, 0, "body cannot be empty"
    
    try:
        # Get all device tokens for this user
        device_tokens = DeviceToken.objects.filter(user=user).values_list('fcm_token', flat=True)
        
        if not device_tokens:
            return 0, 0, f"No device tokens found for user {user.user_name}"
        
        tokens_list = list(device_tokens)
        
        result = send_push_notification_with_retry(
            fcm_tokens=tokens_list,
            title=title.strip(),
            body=body.strip(),
            data_payload=data or {}
        )
        
        success_count = result.get('success', 0)
        total_count = len(tokens_list)
        
        msg = f"Sent to {success_count}/{total_count} devices for user {user.user_name}"
        return success_count, total_count, msg
    
    except Exception as e:
        logger.error(f"Error sending notification to user {user.user_id}: {str(e)}")
        return 0, 0, f"Error: {str(e)}"


def send_to_all(
    title: str,
    body: str,
    data: Optional[Dict] = None
) -> Tuple[int, int, str]:
    """
    Send push notification to ALL registered devices.
    
    Use with caution - sends to every device in the database.
    
    Args:
        title: Notification title
        body: Notification body
        data: Optional data payload (dict)
    
    Returns:
        Tuple of (success_count: int, total_count: int, message: str)
    
    Example:
        success, total, msg = send_to_all(
            title="System Maintenance",
            body="App will be down for 1 hour",
            data={"maintenance": True}
        )
    """
    if not title or not title.strip():
        return 0, 0, "title cannot be empty"
    
    if not body or not body.strip():
        return 0, 0, "body cannot be empty"
    
    try:
        # Get ALL device tokens
        all_tokens = DeviceToken.objects.values_list('fcm_token', flat=True)
        
        if not all_tokens:
            return 0, 0, "No device tokens found in database"
        
        tokens_list = list(all_tokens)
        
        logger.info(f"Sending notification to {len(tokens_list)} devices")
        
        result = send_push_notification_with_retry(
            fcm_tokens=tokens_list,
            title=title.strip(),
            body=body.strip(),
            data_payload=data or {}
        )
        
        success_count = result.get('success', 0)
        total_count = len(tokens_list)
        
        msg = f"Sent to {success_count}/{total_count} devices"
        logger.info(msg)
        
        return success_count, total_count, msg
    
    except Exception as e:
        logger.error(f"Error sending notification to all: {str(e)}")
        return 0, 0, f"Error: {str(e)}"


def send_to_multiple_users(
    user_ids: List[int],
    title: str,
    body: str,
    data: Optional[Dict] = None
) -> Tuple[int, int, str]:
    """
    Send push notification to multiple specific users.
    
    Args:
        user_ids: List of Member IDs
        title: Notification title
        body: Notification body
        data: Optional data payload (dict)
    
    Returns:
        Tuple of (success_count: int, total_count: int, message: str)
    
    Example:
        success, total, msg = send_to_multiple_users(
            user_ids=[1, 2, 3],
            title="Event Reminder",
            body="Workshop starts in 1 hour",
            data={"event_id": "456"}
        )
    """
    if not user_ids:
        return 0, 0, "user_ids list cannot be empty"
    
    if not title or not title.strip():
        return 0, 0, "title cannot be empty"
    
    if not body or not body.strip():
        return 0, 0, "body cannot be empty"
    
    try:
        # Get all device tokens for specified users
        device_tokens = DeviceToken.objects.filter(
            user_id__in=user_ids
        ).values_list('fcm_token', flat=True)
        
        if not device_tokens:
            return 0, 0, f"No device tokens found for specified users"
        
        tokens_list = list(device_tokens)
        
        result = send_push_notification_with_retry(
            fcm_tokens=tokens_list,
            title=title.strip(),
            body=body.strip(),
            data_payload=data or {}
        )
        
        success_count = result.get('success', 0)
        total_count = len(tokens_list)
        
        msg = f"Sent to {success_count}/{total_count} devices across {len(user_ids)} users"
        return success_count, total_count, msg
    
    except Exception as e:
        logger.error(f"Error sending notification to multiple users: {str(e)}")
        return 0, 0, f"Error: {str(e)}"
