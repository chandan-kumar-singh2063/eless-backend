"""
Firebase Client for Firestore and FCM Integration

Handles:
- Firebase Admin SDK initialization
- Firestore device token storage/retrieval
- FCM push notification sending
"""

import firebase_admin
from firebase_admin import credentials, firestore, messaging
from django.conf import settings
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger('authentication')

# Initialize Firebase Admin SDK
_firebase_app = None
_firestore_client = None


def initialize_firebase():
    """Initialize Firebase Admin SDK with service account"""
    global _firebase_app, _firestore_client
    
    if _firebase_app is None:
        try:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            _firebase_app = firebase_admin.initialize_app(cred)
            _firestore_client = firestore.client()
            logger.info("Firebase Admin SDK initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            raise
    
    return _firestore_client


def get_firestore_client():
    """Get Firestore client instance"""
    if _firestore_client is None:
        return initialize_firebase()
    return _firestore_client


# ==================== Device Token Management ====================

def save_device_token(user_id: str, device_id: str, fcm_token: str, platform: str = "unknown") -> bool:
    """
    Save or update device FCM token in Firestore
    
    Structure: /users/{user_id}/devices/{device_id}
    
    Args:
        user_id: Unique user identifier
        device_id: UUID of the device
        fcm_token: Firebase Cloud Messaging token
        platform: Device platform (android/ios)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        db = get_firestore_client()
        
        device_ref = db.collection('users').document(user_id).collection('devices').document(device_id)
        
        device_data = {
            'fcm_token': fcm_token,
            'platform': platform,
            'updated_at': firestore.SERVER_TIMESTAMP,
        }
        
        device_ref.set(device_data, merge=True)
        
        logger.info(f"Device token saved: user_id={user_id}, device_id={device_id}, platform={platform}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save device token: {str(e)}")
        return False


def delete_device_token(user_id: str, device_id: str) -> bool:
    """
    Delete device FCM token from Firestore
    
    Args:
        user_id: Unique user identifier
        device_id: UUID of the device
    
    Returns:
        True if successful, False otherwise
    """
    try:
        db = get_firestore_client()
        
        device_ref = db.collection('users').document(user_id).collection('devices').document(device_id)
        device_ref.delete()
        
        logger.info(f"Device token deleted: user_id={user_id}, device_id={device_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to delete device token: {str(e)}")
        return False


def get_tokens_for_user(user_id: str) -> List[str]:
    """
    Get all FCM tokens for a specific user
    
    Args:
        user_id: Unique user identifier
    
    Returns:
        List of FCM tokens
    """
    try:
        db = get_firestore_client()
        
        devices_ref = db.collection('users').document(user_id).collection('devices')
        devices = devices_ref.stream()
        
        tokens = []
        for device in devices:
            device_data = device.to_dict()
            if 'fcm_token' in device_data:
                tokens.append(device_data['fcm_token'])
        
        logger.info(f"Retrieved {len(tokens)} tokens for user_id={user_id}")
        return tokens
        
    except Exception as e:
        logger.error(f"Failed to get tokens for user: {str(e)}")
        return []


def get_all_tokens() -> List[str]:
    """
    Get all FCM tokens from all users
    
    Returns:
        List of all FCM tokens
    """
    try:
        db = get_firestore_client()
        
        users_ref = db.collection('users')
        users = users_ref.stream()
        
        all_tokens = []
        for user in users:
            devices_ref = user.reference.collection('devices')
            devices = devices_ref.stream()
            
            for device in devices:
                device_data = device.to_dict()
                if 'fcm_token' in device_data:
                    all_tokens.append(device_data['fcm_token'])
        
        logger.info(f"Retrieved {len(all_tokens)} total tokens")
        return all_tokens
        
    except Exception as e:
        logger.error(f"Failed to get all tokens: {str(e)}")
        return []


# ==================== Push Notification Sending ====================

def send_push_notification(title: str, body: str, tokens: List[str], data: Optional[Dict] = None) -> Dict:
    """
    Send push notification to multiple devices using FCM
    
    Args:
        title: Notification title
        body: Notification body
        tokens: List of FCM tokens
        data: Optional additional data payload
    
    Returns:
        Dictionary with success_count and failure_count
    """
    if not tokens:
        logger.warning("No tokens provided for push notification")
        return {'success_count': 0, 'failure_count': 0, 'failed_tokens': []}
    
    try:
        # Create notification message
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=title,
                body=body,
            ),
            data=data or {},
            tokens=tokens,
        )
        
        # Send multicast message
        response = messaging.send_multicast(message)
        
        # Log results
        logger.info(
            f"Push notification sent: "
            f"success={response.success_count}, "
            f"failure={response.failure_count}"
        )
        
        # Collect failed tokens for cleanup
        failed_tokens = []
        if response.failure_count > 0:
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    failed_tokens.append(tokens[idx])
                    logger.warning(f"Failed to send to token: {resp.exception}")
        
        return {
            'success_count': response.success_count,
            'failure_count': response.failure_count,
            'failed_tokens': failed_tokens,
        }
        
    except Exception as e:
        logger.error(f"Failed to send push notification: {str(e)}")
        return {
            'success_count': 0,
            'failure_count': len(tokens),
            'failed_tokens': tokens,
            'error': str(e)
        }


def send_push_to_user(user_id: str, title: str, body: str, data: Optional[Dict] = None) -> Dict:
    """
    Send push notification to all devices of a specific user
    
    Args:
        user_id: Unique user identifier
        title: Notification title
        body: Notification body
        data: Optional additional data payload
    
    Returns:
        Dictionary with send results
    """
    tokens = get_tokens_for_user(user_id)
    
    if not tokens:
        logger.warning(f"No tokens found for user_id={user_id}")
        return {'success_count': 0, 'failure_count': 0, 'message': 'No devices found'}
    
    return send_push_notification(title, body, tokens, data)


def send_push_to_all_users(title: str, body: str, data: Optional[Dict] = None) -> Dict:
    """
    Send push notification to all users
    
    Args:
        title: Notification title
        body: Notification body
        data: Optional additional data payload
    
    Returns:
        Dictionary with send results
    """
    tokens = get_all_tokens()
    
    if not tokens:
        logger.warning("No tokens found for any users")
        return {'success_count': 0, 'failure_count': 0, 'message': 'No devices found'}
    
    return send_push_notification(title, body, tokens, data)


# ==================== Utility Functions ====================

def get_device_count_for_user(user_id: str) -> int:
    """Get count of devices for a user"""
    try:
        db = get_firestore_client()
        devices_ref = db.collection('users').document(user_id).collection('devices')
        devices = list(devices_ref.stream())
        return len(devices)
    except Exception as e:
        logger.error(f"Failed to get device count: {str(e)}")
        return 0


def cleanup_invalid_tokens(failed_tokens: List[str]) -> int:
    """
    Remove invalid tokens from Firestore
    
    Args:
        failed_tokens: List of tokens that failed to send
    
    Returns:
        Number of tokens cleaned up
    """
    # This is a simplified cleanup - in production you'd want to
    # track which user/device each token belongs to
    cleaned = 0
    try:
        db = get_firestore_client()
        users_ref = db.collection('users')
        users = users_ref.stream()
        
        for user in users:
            devices_ref = user.reference.collection('devices')
            devices = devices_ref.stream()
            
            for device in devices:
                device_data = device.to_dict()
                if device_data.get('fcm_token') in failed_tokens:
                    device.reference.delete()
                    cleaned += 1
                    logger.info(f"Cleaned up invalid token for device {device.id}")
        
        return cleaned
        
    except Exception as e:
        logger.error(f"Failed to cleanup invalid tokens: {str(e)}")
        return 0
