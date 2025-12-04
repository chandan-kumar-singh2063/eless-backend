"""
FCM Token API Serializers

Handles validation for FCM token registration/unregistration.
"""

from rest_framework import serializers


class RegisterFCMTokenSerializer(serializers.Serializer):
    """Serializer for FCM token registration"""
    
    user_unique_id = serializers.CharField(
        required=True,
        max_length=50,
        help_text="User's unique ID (e.g., ROBO-2024-001)"
    )
    
    fcm_token = serializers.CharField(
        required=True,
        help_text="Firebase Cloud Messaging token"
    )
    
    device_id = serializers.CharField(
        required=True,
        max_length=100,
        help_text="Unique device identifier"
    )
    
    platform = serializers.ChoiceField(
        choices=['android', 'ios', 'web', 'unknown'],
        default='unknown',
        required=False,
        help_text="Device platform"
    )
    
    device_model = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        help_text="Device model (e.g., Pixel 6)"
    )
    
    device_manufacturer = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        help_text="Device manufacturer (e.g., Google)"
    )
    
    def validate_fcm_token(self, value):
        """Validate FCM token is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("FCM token cannot be empty")
        return value.strip()
    
    def validate_device_id(self, value):
        """Validate device ID is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("Device ID cannot be empty")
        return value.strip()
    
    def validate_user_unique_id(self, value):
        """Validate user unique ID is not empty"""
        if not value or not value.strip():
            raise serializers.ValidationError("User unique ID cannot be empty")
        return value.strip()


class UnregisterFCMTokenSerializer(serializers.Serializer):
    """Serializer for FCM token unregistration"""
    
    fcm_token = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="FCM token to unregister (optional if device_id provided)"
    )
    
    device_id = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Device ID to unregister (optional if fcm_token provided)"
    )
    
    def validate(self, data):
        """Ensure at least one of fcm_token or device_id is provided"""
        if not data.get('fcm_token') and not data.get('device_id'):
            raise serializers.ValidationError(
                "Either fcm_token or device_id must be provided"
            )
        return data
