"""
Authentication API Views for QR-based JWT Authentication

Implements secure QR login, token refresh with rotation, logout with blacklisting,
and protected profile endpoint.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes, authentication_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from django.conf import settings
from django.utils import timezone
import logging
import uuid

from .models import Member, Device
from .serializers import (
    QRLoginSerializer,
    QRLoginResponseSerializer,
    TokenRefreshSerializer,
    LogoutSerializer,
    MemberSerializer,
    DeviceSerializer,
    SaveDeviceTokenSerializer,
    RemoveDeviceTokenSerializer
)
from . import firebase_client_v2 as firebase_client
from .throttles import (
    QRLoginThrottle,
    TokenRefreshThrottle,
    RegisterDeviceThrottle,
    UnregisterDeviceThrottle,
    PushNotificationThrottle
)

# Configure logging for security events
logger = logging.getLogger('authentication')


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([QRLoginThrottle])
def qr_login(request):
    """
    Member Login Endpoint
    
    Workflow:
    1. Receive user_id from Flutter app
    2. Lookup Member by user_id
    3. Validate member is active
    4. Issue JWT tokens using SimpleJWT (with rotation enabled)
    5. Create/update Device record if device_id provided
    6. Return tokens and user profile
    
    POST /api/auth/qr-login/
    Body: {
        "user_id": "ROBO-2024-001",  # Unique ID provided by admin
        "device_id": "uuid-optional",
        "platform": "android",
        "device_name": "Samsung Galaxy S21"
    }
    
    Response: {
        "access": "jwt_access_token",
        "refresh": "jwt_refresh_token",
        "user": { member profile },
        "expires_in": 900,
        "device_id": "uuid"
    }
    """
    
    serializer = QRLoginSerializer(data=request.data)
    
    if not serializer.is_valid():
        logger.warning(f"QR login validation failed: {serializer.errors}")
        return Response(
            {'error': 'Invalid request data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user_id = serializer.validated_data['user_id']
    device_id = serializer.validated_data.get('device_id')
    platform = serializer.validated_data.get('platform', 'unknown')
    device_name = serializer.validated_data.get('device_name', '')
    
    # Lookup member by user_id
    try:
        member = Member.objects.get(user_id=user_id)
    except Member.DoesNotExist:
        logger.warning(f"QR login failed: user_id '{user_id}' not found")
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Check if member is active
    if not member.is_active:
        logger.warning(f"QR login failed: user_id '{user_id}' is inactive")
        return Response(
            {'error': 'Account is inactive'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    
    # Generate JWT tokens using SimpleJWT
    # This respects ROTATE_REFRESH_TOKENS and BLACKLIST_AFTER_ROTATION settings
    refresh = RefreshToken()
    refresh['user_id'] = member.id
    refresh['user_name'] = member.user_name
    refresh['member_user_id'] = member.user_id
    
    # Get access token lifetime from settings
    access_token_lifetime = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
    expires_in = int(access_token_lifetime.total_seconds())
    
    # Handle device tracking if device_id provided (optimized - single query)
    device = None
    if device_id:
        try:
            # Use update_or_create for single query instead of get_or_create + save
            device, created = Device.objects.update_or_create(
                member=member,
                device_id=device_id,
                defaults={
                    'platform': platform,
                    'device_name': device_name,
                    'last_refresh_token_jti': str(refresh['jti']),
                    'is_logged_out': False,
                }
            )
            
            logger.info(
                f"QR login successful: user_id='{user_id}', "
                f"device_id='{device_id}', platform='{platform}'"
            )
        except Exception as e:
            logger.error(f"Device tracking failed: {str(e)}")
            # Continue without device tracking
    else:
        logger.info(f"QR login successful: user_id='{user_id}' (no device tracking)")
    
    # Prepare response with Flutter-compatible user data
    from .serializers import FlutterMemberSerializer
    response_data = {
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'user': FlutterMemberSerializer(member).data,
        'expires_in': expires_in,
    }
    
    if device_id:
        response_data['device_id'] = str(device_id)
    
    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def token_refresh(request):
    """
    Token Refresh Endpoint (FIXED - updates device JTI)
    
    Workflow:
    1. Receive refresh token + optional device_id
    2. Validate and decode refresh token
    3. Issue new access token and refresh token (rotation)
    4. Update device.last_refresh_token_jti (CRITICAL FIX)
    5. Blacklist old refresh token
    
    POST /api/auth/token/refresh/
    Body: {
        "refresh": "jwt_refresh_token",
        "device_id": "uuid-optional"
    }
    
    Response: {
        "access": "new_jwt_access_token",
        "refresh": "new_jwt_refresh_token"
    }
    """
    
    serializer = TokenRefreshSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid request data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    refresh_token = serializer.validated_data['refresh']
    device_id = request.data.get('device_id')  # Optional device_id
    
    try:
        # Decode and validate refresh token
        refresh = RefreshToken(refresh_token)
        
        # Get user info from token
        user_id = refresh.get('user_id')
        
        # Generate new tokens
        new_refresh = RefreshToken()
        new_refresh['user_id'] = user_id
        new_refresh['user_name'] = refresh.get('user_name')
        new_refresh['member_user_id'] = refresh.get('member_user_id')
        new_jti = str(new_refresh['jti'])
        
        # CRITICAL FIX: Update device.last_refresh_token_jti
        if device_id:
            try:
                device = Device.objects.get(device_id=device_id, member_id=user_id)
                device.last_refresh_token_jti = new_jti
                device.last_seen = timezone.now()
                device.save(update_fields=['last_refresh_token_jti', 'last_seen'])
                logger.info(f"Device {device_id} JTI updated on refresh")
            except Device.DoesNotExist:
                logger.warning(f"Device {device_id} not found for token refresh")
        
        # Blacklist the old refresh token
        if settings.SIMPLE_JWT['BLACKLIST_AFTER_ROTATION']:
            try:
                refresh.blacklist()
                logger.info(f"Token rotated for user_id={user_id}")
            except Exception as e:
                logger.error(f"Failed to blacklist token: {str(e)}")
        
        response_data = {
            'access': str(new_refresh.access_token),
            'refresh': str(new_refresh),
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except TokenError as e:
        logger.warning(f"Token refresh failed: {str(e)}")
        return Response(
            {'error': 'Invalid or expired refresh token'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        return Response(
            {'error': 'Token refresh failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@authentication_classes([])  # Disable authentication for logout
@permission_classes([AllowAny])
def logout(request):
    """
    Logout Endpoint (FIXED - handles failures gracefully)
    
    Workflow:
    1. Receive refresh token + optional device_id
    2. Blacklist refresh token (logout from backend)
    3. Delete device record (if device_id provided)
    4. Remove FCM token from Firestore (if device_id provided)
    
    Each operation is attempted independently to ensure partial success.
    No authentication required - validates refresh token instead.
    
    POST /api/auth/logout/
    Body: {
        "refresh": "jwt_refresh_token",
        "device_id": "uuid-optional"
    }
    
    Response: {
        "message": "Logged out successfully",
        "operations": {
            "token_blacklisted": true,
            "device_deleted": true,
            "fcm_removed": true
        }
    }
    """
    
    serializer = LogoutSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid request data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    refresh_token = serializer.validated_data['refresh']
    device_id = serializer.validated_data.get('device_id')
    
    operation_status = {
        'token_blacklisted': False,
        'device_deleted': False,
        'fcm_removed': False
    }
    
    # Operation 1: Blacklist refresh token
    user_id = None
    member_user_id = None
    
    try:
        refresh = RefreshToken(refresh_token)
        user_id = refresh.get('user_id')
        member_user_id = refresh.get('member_user_id')
        
        try:
            refresh.blacklist()
            operation_status['token_blacklisted'] = True
            logger.info(f"Token blacklisted for user_id={user_id}")
        except Exception as e:
            logger.warning(f"Token already blacklisted or invalid: {str(e)}")
            operation_status['token_blacklisted'] = True  # Idempotent
    except TokenError as e:
        logger.info(f"Logout with invalid token: {str(e)}")
        operation_status['token_blacklisted'] = True  # Idempotent
    
    # Operation 2: Delete device record from PostgreSQL (optimized - single query)
    if device_id and user_id:
        try:
            # Use delete() directly - no need to fetch first
            deleted_count, _ = Device.objects.filter(
                device_id=device_id,
                member_id=user_id
            ).delete()
            
            operation_status['device_deleted'] = True
            if deleted_count > 0:
                logger.info(f"Device {device_id} deleted from PostgreSQL")
        except Exception as e:
            logger.error(f"Failed to delete device from PostgreSQL: {str(e)}")
    else:
        operation_status['device_deleted'] = True  # No device_id = no-op
    
    # Operation 3 & 4: Remove DeviceToken from database (optimized - single query)
    if device_id and user_id:
        try:
            from .models import DeviceToken
            deleted_count, _ = DeviceToken.objects.filter(
                user_id=user_id,
                device_id=device_id
            ).delete()
            
            if deleted_count > 0:
                logger.info(f"DeviceToken removed for device {device_id}")
        except Exception as e:
            logger.error(f"Failed to remove DeviceToken: {str(e)}")
    
    # Operation 5: Remove FCM token from Firestore (ASYNC - don't wait)
    # Make this async to not block the response
    if device_id and member_user_id:
        try:
            from threading import Thread
            from .firebase_client import delete_device_token
            
            # Run in background thread to not block response
            def remove_fcm_async():
                try:
                    delete_device_token(str(member_user_id), str(device_id))
                    logger.info(f"FCM token removed for device {device_id}")
                except Exception as e:
                    logger.error(f"Failed to remove FCM token from Firestore: {str(e)}")
            
            Thread(target=remove_fcm_async, daemon=True).start()
            operation_status['fcm_removed'] = True  # Optimistic
        except Exception as e:
            logger.error(f"Failed to start FCM removal thread: {str(e)}")
    else:
        operation_status['fcm_removed'] = True  # No device_id = no-op
    
    return Response({
        'detail': 'Logged out successfully',
        'operations': operation_status
    }, status=status.HTTP_200_OK)


# Device Token Management Endpoints
@permission_classes([IsAuthenticated])
def profile(request):
    """
    Get Current User Profile
    
    Protected endpoint to verify JWT authentication works.
    Returns member profile and active devices.
    
    GET /api/auth/profile/
    Headers: Authorization: Bearer <access_token>
    
    Response: {
        "member": { member profile },
        "devices": [ list of devices ]
    }
    """
    
    try:
        # Get member ID from JWT token
        # The JWT authentication middleware populates request.user
        # But since we're using Member model, we need to get it from token
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return Response(
                {'error': 'Invalid authorization header'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        token = auth_header.split(' ')[1]
        from rest_framework_simplejwt.tokens import AccessToken
        access_token = AccessToken(token)
        
        member_id = access_token.get('user_id')
        
        # Get member
        member = Member.objects.get(id=member_id)
        
        # Get active devices
        devices = member.get_active_devices()
        
        response_data = {
            'member': MemberSerializer(member).data,
            'devices': DeviceSerializer(devices, many=True).data,
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Member.DoesNotExist:
        logger.warning(f"Profile access: member not found")
        return Response(
            {'error': 'Member not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except TokenError as e:
        logger.warning(f"Profile access: invalid token - {str(e)}")
        return Response(
            {'error': 'Invalid access token'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        logger.error(f"Profile error: {str(e)}")
        return Response(
            {'error': 'Failed to fetch profile'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_device_token(request):
    """
    Save Device FCM Token to Firestore
    
    This endpoint is called after successful login to register the device
    for push notifications. The FCM token is stored in Firestore at:
    /users/{user_id}/devices/{device_id}
    
    POST /api/device/save-token/
    Headers: Authorization: Bearer <access_token>
    Body: {
        "device_id": "uuid",
        "fcm_token": "firebase_cloud_messaging_token",
        "platform": "android|ios|web"
    }
    
    Response: {
        "success": true,
        "message": "Device token saved successfully"
    }
    """
    
    serializer = SaveDeviceTokenSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid request data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Get member ID from JWT token
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.split(' ')[1]
        from rest_framework_simplejwt.tokens import AccessToken
        access_token = AccessToken(token)
        member_id = access_token.get('user_id')
        
        # Get validated data
        device_id = str(serializer.validated_data['device_id'])
        fcm_token = serializer.validated_data['fcm_token']
        platform = serializer.validated_data['platform']
        
        # Verify device belongs to this member
        try:
            device = Device.objects.get(device_id=device_id, member_id=member_id)
            
            # Update device's last_seen timestamp
            device.last_seen = timezone.now()
            device.save(update_fields=['last_seen'])
            
        except Device.DoesNotExist:
            logger.warning(
                f"Device {device_id} not found for member {member_id}. "
                "User must login first before saving FCM token."
            )
            return Response(
                {
                    'error': 'Device not found',
                    'detail': 'Please login first to register device'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Save FCM token to Firestore
        firebase_client.save_device_token(
            user_id=str(member_id),
            device_id=device_id,
            fcm_token=fcm_token,
            platform=platform
        )
        
        logger.info(
            f"FCM token saved: user_id={member_id}, "
            f"device_id={device_id}, platform={platform}"
        )
        
        return Response(
            {
                'success': True,
                'message': 'Device token saved successfully'
            },
            status=status.HTTP_200_OK
        )
        
    except TokenError as e:
        logger.warning(f"Save device token: invalid token - {str(e)}")
        return Response(
            {'error': 'Invalid access token'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        logger.error(f"Failed to save device token: {str(e)}")
        return Response(
            {'error': 'Failed to save device token', 'detail': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def remove_device_token(request):
    """
    Remove Device FCM Token from Firestore
    
    This endpoint is called during logout to stop sending push notifications
    to the device. The device token is removed from Firestore.
    
    POST /api/device/remove-token/
    Headers: Authorization: Bearer <access_token>
    Body: {
        "device_id": "uuid"
    }
    
    Response: {
        "success": true,
        "message": "Device token removed successfully"
    }
    
    Note: This endpoint is idempotent. If the token doesn't exist in Firestore,
    it still returns 200 OK.
    """
    
    serializer = RemoveDeviceTokenSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': 'Invalid request data', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Get member ID from JWT token
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.split(' ')[1]
        from rest_framework_simplejwt.tokens import AccessToken
        access_token = AccessToken(token)
        member_id = access_token.get('user_id')
        
        # Get validated data
        device_id = str(serializer.validated_data['device_id'])
        
        # Remove FCM token from Firestore
        firebase_client.delete_device_token(
            user_id=str(member_id),
            device_id=device_id
        )
        
        logger.info(
            f"FCM token removed: user_id={member_id}, device_id={device_id}"
        )
        
        return Response(
            {
                'success': True,
                'message': 'Device token removed successfully'
            },
            status=status.HTTP_200_OK
        )
        
    except TokenError as e:
        logger.warning(f"Remove device token: invalid token - {str(e)}")
        return Response(
            {'error': 'Invalid access token'},
            status=status.HTTP_401_UNAUTHORIZED
        )
    except Exception as e:
        # Still return success for idempotency
        logger.info(f"Remove device token: {str(e)}")
        return Response(
            {
                'success': True,
                'message': 'Device token removed successfully'
            },
            status=status.HTTP_200_OK
        )


# ============================================================================
# DEVICE TOKEN MANAGEMENT (Multi-Device Support)
# ============================================================================

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegisterDeviceThrottle])
def register_device(request):
    """
    Register Device Token (POST /auth/register-device/)
    
    ✅ PRODUCTION FIX: Rate-limited to 10/min per IP
    
    Multi-device support:
    - One user can have multiple device tokens
    - Updates existing token if same device_id found
    - Does NOT delete other device tokens
    
    Request Body:
        {
            "unique_id": "ROBO-2024-001",
            "device_id": "uuid-or-device-fingerprint",
            "fcm_token": "firebase-token",
            "platform": "android",
            "model": "Pixel 7" (optional)
        }
    
    Response:
        {
            "success": true,
            "message": "Device registered successfully",
            "device_id": "abc123...",
            "is_new": true/false
        }
    """
    from .serializers import RegisterDeviceSerializer
    from .models import DeviceToken
    
    # DEBUG: Log the incoming request
    logger.info(f"🔔 register_device called - Body: {request.data}")
    
    serializer = RegisterDeviceSerializer(data=request.data)
    
    if not serializer.is_valid():
        logger.warning(f"❌ register_device validation failed: {serializer.errors}")
        return Response(
            {'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    unique_id = serializer.validated_data['unique_id']
    device_id = serializer.validated_data['device_id']
    fcm_token = serializer.validated_data['fcm_token']
    platform = serializer.validated_data['platform']
    device_model = serializer.validated_data.get('model', '')
    
    try:
        # Find member by unique_id
        try:
            member = Member.objects.get(user_id=unique_id, is_active=True)
        except Member.DoesNotExist:
            logger.warning(f"Register device: Member not found - {unique_id}")
            return Response(
                {'error': 'Invalid unique_id'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update existing or create new device token
        device_token, created = DeviceToken.objects.update_or_create(
            user=member,
            device_id=device_id,
            defaults={
                'fcm_token': fcm_token,
                'platform': platform,
                'device_model': device_model,
            }
        )
        
        # Also save to Firestore for push notifications
        firebase_client.save_device_token(
            user_id=member.user_id,
            device_id=device_id,
            fcm_token=fcm_token,
            platform=platform,
            device_model=device_model
        )
        
        action = "registered" if created else "updated"
        logger.info(
            f"Device {action}: user={member.user_name}, "
            f"device_id={device_id[:8]}..., platform={platform}"
        )
        
        return Response(
            {
                'success': True,
                'message': f'Device {action} successfully',
                'device_id': device_id,
                'is_new': created
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )
    
    except Exception as e:
        logger.error(f"Error registering device: {str(e)}")
        return Response(
            {'error': 'Failed to register device'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([UnregisterDeviceThrottle])
def unregister_device(request):
    """
    Unregister Device Token (POST /auth/unregister-device/)
    
    ✅ PRODUCTION FIX: Rate-limited to 10/min per IP
    
    Removes ONLY the specified device token.
    Does NOT affect other devices.
    
    Request Body:
        {
            "unique_id": "ROBO-2024-001",
            "device_id": "uuid-or-device-fingerprint"
        }
    
    Response:
        {
            "success": true,
            "message": "Device unregistered successfully"
        }
    """
    from .serializers import UnregisterDeviceSerializer
    from .models import DeviceToken
    
    serializer = UnregisterDeviceSerializer(data=request.data)
    
    if not serializer.is_valid():
        return Response(
            {'error': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    unique_id = serializer.validated_data['unique_id']
    device_id = serializer.validated_data['device_id']
    
    try:
        # Find member by unique_id
        try:
            member = Member.objects.get(user_id=unique_id, is_active=True)
        except Member.DoesNotExist:
            # Return success for idempotency (device is "unregistered")
            logger.warning(f"Unregister device: Member not found - {unique_id}")
            return Response(
                {
                    'success': True,
                    'message': 'Device unregistered successfully'
                },
                status=status.HTTP_200_OK
            )
        
        # Delete device token (if exists)
        deleted_count, _ = DeviceToken.objects.filter(
            user=member,
            device_id=device_id
        ).delete()
        
        if deleted_count > 0:
            logger.info(
                f"Device unregistered: user={member.user_name}, "
                f"device_id={device_id[:8]}..."
            )
        else:
            logger.info(
                f"Device already unregistered: user={member.user_name}, "
                f"device_id={device_id[:8]}..."
            )
        
        return Response(
            {
                'success': True,
                'message': 'Device unregistered successfully'
            },
            status=status.HTTP_200_OK
        )
    
    except Exception as e:
        # Return success for idempotency
        logger.error(f"Error unregistering device: {str(e)}")
        return Response(
            {
                'success': True,
                'message': 'Device unregistered successfully'
            },
            status=status.HTTP_200_OK
        )
