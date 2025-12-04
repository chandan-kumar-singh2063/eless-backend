"""
Serializers for Authentication API

Handles QR login, token refresh, logout, profile, and device token management.
"""

from rest_framework import serializers
from .models import Member, Device, DeviceToken
import uuid


class MemberSerializer(serializers.Serializer):
    """Serializer for Member profile data"""
    
    id = serializers.IntegerField(read_only=True)
    user_name = serializers.CharField(read_only=True)
    user_id = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    active_devices_count = serializers.SerializerMethodField()
    
    def get_active_devices_count(self, obj):
        """Return count of active devices for this member"""
        return obj.get_active_devices().count()


class FlutterMemberSerializer(serializers.Serializer):
    """
    Flutter-compatible serializer for Member profile data.
    Maps backend field names to Flutter's expected field names.
    Optimized to avoid extra database queries during login.
    """
    
    id = serializers.SerializerMethodField()
    fullName = serializers.CharField(source='user_name', read_only=True)
    email = serializers.SerializerMethodField()
    user_id = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    
    def get_id(self, obj):
        """Return ID as string for Flutter"""
        return str(obj.id)
    
    def get_email(self, obj):
        """Generate email from user_id if not available"""
        # Since we don't have email in model, generate a placeholder
        # You can add email field to Member model later if needed
        return f"{obj.user_id.lower()}@roboticsclub.edu"


class DeviceSerializer(serializers.ModelSerializer):
    """Serializer for Device data"""
    
    member_name = serializers.CharField(source='member.user_name', read_only=True)
    
    class Meta:
        model = Device
        fields = [
            'id', 'member', 'member_name', 'device_id', 'platform', 
            'device_name', 'last_seen', 'is_logged_out', 'created_at', 'is_new'
        ]
        read_only_fields = ['id', 'member', 'last_seen', 'created_at']


class QRLoginSerializer(serializers.Serializer):
    """
    Serializer for login request.
    
    The user_id is the unique identifier shared with the member.
    device_id is optional but recommended for device tracking.
    """
    
    user_id = serializers.CharField(
        required=True,
        max_length=100,
        help_text="Unique user ID for authentication"
    )
    
    device_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Unique device identifier from mobile app"
    )
    
    platform = serializers.ChoiceField(
        choices=['android', 'ios', 'web', 'unknown'],
        default='unknown',
        required=False,
        help_text="Device platform"
    )
    
    device_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=200,
        help_text="Human-readable device name"
    )
    
    def validate_user_id(self, value):
        """Validate that user_id is not empty and properly formatted"""
        if not value or value.strip() == '':
            raise serializers.ValidationError("user_id cannot be empty")
        return value.strip()


class QRLoginResponseSerializer(serializers.Serializer):
    """
    Serializer for QR login successful response.
    
    Returns JWT tokens and user information.
    """
    
    access = serializers.CharField(help_text="JWT access token")
    refresh = serializers.CharField(help_text="JWT refresh token")
    user = MemberSerializer(help_text="User profile data")
    expires_in = serializers.IntegerField(help_text="Access token expiry in seconds")
    device_id = serializers.UUIDField(
        required=False,
        help_text="Device ID (returned if device tracking is enabled)"
    )


class TokenRefreshSerializer(serializers.Serializer):
    """
    Serializer for token refresh request.
    
    Uses SimpleJWT's built-in refresh mechanism with rotation.
    """
    
    refresh = serializers.CharField(
        required=True,
        help_text="Refresh token to exchange for new access token"
    )
    
    def validate_refresh(self, value):
        """Validate that refresh token is not empty"""
        if not value or value.strip() == '':
            raise serializers.ValidationError("refresh token cannot be empty")
        return value


class LogoutSerializer(serializers.Serializer):
    """
    Serializer for logout request.
    
    Blacklists the refresh token to prevent reuse.
    """
    
    refresh = serializers.CharField(
        required=True,
        help_text="Refresh token to blacklist"
    )
    
    device_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Device ID to logout (optional)"
    )
    
    def validate_refresh(self, value):
        """Validate that refresh token is not empty"""
        if not value or value.strip() == '':
            raise serializers.ValidationError("refresh token cannot be empty")
        return value


class SaveDeviceTokenSerializer(serializers.Serializer):
    """
    Serializer for saving device FCM token to Firestore.
    
    This is called after successful login to register device for push notifications.
    """
    
    device_id = serializers.UUIDField(
        required=True,
        help_text="Unique device identifier (must match login device_id)"
    )
    
    fcm_token = serializers.CharField(
        required=True,
        max_length=500,
        help_text="Firebase Cloud Messaging token from device"
    )
    
    platform = serializers.ChoiceField(
        choices=['android', 'ios', 'web'],
        required=True,
        help_text="Device platform"
    )
    
    def validate_fcm_token(self, value):
        """Validate that FCM token is not empty"""
        if not value or value.strip() == '':
            raise serializers.ValidationError("fcm_token cannot be empty")
        return value.strip()


class RemoveDeviceTokenSerializer(serializers.Serializer):
    """
    Serializer for removing device FCM token from Firestore.
    
    This is called during logout to stop sending push notifications to this device.
    """
    
    device_id = serializers.UUIDField(
        required=True,
        help_text="Unique device identifier to remove from Firestore"
    )


class DeviceTokenSerializer(serializers.ModelSerializer):
    """Serializer for DeviceToken model"""
    
    user_name = serializers.CharField(source='user.user_name', read_only=True)
    
    class Meta:
        model = DeviceToken
        fields = [
            'id', 'user', 'user_name', 'device_id', 'fcm_token', 
            'platform', 'device_model', 'created_at', 'last_updated'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'last_updated']


class RegisterDeviceSerializer(serializers.Serializer):
    """
    Serializer for device registration (POST /auth/register-device/).
    
    Receives device info and FCM token from Flutter app.
    Updates existing record if same device_id found.
    """
    
    unique_id = serializers.CharField(
        required=True,
        help_text="Member's unique_id (user_id) for authentication"
    )
    
    device_id = serializers.CharField(
        required=True,
        max_length=255,
        help_text="Unique device identifier (UUID or device fingerprint)"
    )
    
    fcm_token = serializers.CharField(
        required=True,
        help_text="Firebase Cloud Messaging token"
    )
    
    platform = serializers.ChoiceField(
        choices=['android', 'ios', 'web'],
        required=True,
        help_text="Device platform"
    )
    
    model = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=200,
        help_text="Device model (e.g., 'Pixel 7', 'iPhone 14 Pro')"
    )
    
    def validate_device_id(self, value):
        """Validate device_id is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("device_id cannot be empty")
        return value.strip().lower()
    
    def validate_fcm_token(self, value):
        """Validate fcm_token is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("fcm_token cannot be empty")
        return value.strip()


class UnregisterDeviceSerializer(serializers.Serializer):
    """
    Serializer for device unregistration (POST /auth/unregister-device/).
    
    Removes specific device token, does NOT affect other devices.
    """
    
    unique_id = serializers.CharField(
        required=True,
        help_text="Member's unique_id (user_id) for authentication"
    )
    
    device_id = serializers.CharField(
        required=True,
        max_length=255,
        help_text="Unique device identifier to unregister"
    )
    
    def validate_device_id(self, value):
        """Validate device_id is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("device_id cannot be empty")
        return value.strip().lower()
