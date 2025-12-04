"""
Custom Throttle Classes for API Rate Limiting

AUDIT FIXES:
✅ Brute-force protection for QR login
✅ Different limits for different endpoints
✅ Token refresh throttling
✅ Device registration throttling
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class QRLoginThrottle(AnonRateThrottle):
    """
    Throttle for QR login endpoint
    
    AUDIT: Prevents brute-force attacks on user_id scanning
    Rate: 10 attempts per minute per IP
    """
    rate = '10/minute'
    scope = 'qr_login'


class TokenRefreshThrottle(UserRateThrottle):
    """
    Throttle for token refresh endpoint
    
    AUDIT: Prevents token refresh spam
    Rate: 30 attempts per minute per user
    """
    rate = '30/minute'
    scope = 'token_refresh'


class DeviceRegistrationThrottle(UserRateThrottle):
    """
    Throttle for device token registration
    
    AUDIT: Prevents FCM token spam
    Rate: 20 attempts per minute per user
    """
    rate = '20/minute'
    scope = 'device_registration'


class PushNotificationThrottle(UserRateThrottle):
    """
    Throttle for push notification sending (admin only)
    
    AUDIT: Prevents push notification spam
    Rate: 100 attempts per hour per user
    """
    rate = '100/hour'
    scope = 'push_notification'


class RegisterDeviceThrottle(AnonRateThrottle):
    """
    Throttle for device registration endpoint
    
    PRODUCTION FIX: Prevents duplicate FCM token spam
    Rate: 10 attempts per minute per IP (for unauthenticated)
    """
    rate = '10/minute'
    scope = 'register_device'


class UnregisterDeviceThrottle(AnonRateThrottle):
    """
    Throttle for device unregistration endpoint
    
    PRODUCTION FIX: Prevents unregister spam
    Rate: 10 attempts per minute per IP (for unauthenticated)
    """
    rate = '10/minute'
    scope = 'unregister_device'
