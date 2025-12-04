"""
Authentication Models for QR-based JWT Authentication System

This module defines Member and Device models for secure QR code authentication.
Members are created via Django Admin with user_name and user_id (the QR payload).
"""

from django.db import models
from django.utils import timezone
import uuid


class Member(models.Model):
    """
    Member model for authentication.
    
    The user_id is a unique identifier used for authentication.
    Admins create members by providing only user_name and user_id.
    The unique_id is then shared with the member for login via Flutter app.
    """
    
    user_name = models.CharField(
        max_length=200,
        help_text="Display name of the member"
    )
    
    user_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Unique identifier for authentication (e.g., 'ROBO-2024-001')"
    )
    
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive members cannot authenticate"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when member was created"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when member was last updated"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Member'
        verbose_name_plural = 'Members'
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.user_name} ({self.user_id})"
    
    def get_active_devices(self):
        """Return all active devices for this member"""
        return self.devices.filter(is_logged_out=False)


class Device(models.Model):
    """
    Device model to track member devices and their tokens.
    
    AUDIT FIXED:
    - Immutable device_id per install
    - Added device_model, os_version for analytics
    - Normalized validation in save()
    - FCM token stored in Firestore only
    - Uninstall detection via device_id matching
    """
    
    PLATFORM_CHOICES = [
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('web', 'Web'),
        ('unknown', 'Unknown'),
    ]
    
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='devices',
        help_text="Member who owns this device"
    )
    
    device_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Immutable device identifier from mobile app (UUID or device fingerprint)"
    )
    
    platform = models.CharField(
        max_length=20,
        choices=PLATFORM_CHOICES,
        default='unknown',
        help_text="Device platform (Android, iOS, Web)"
    )
    
    device_name = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Human-readable device name (e.g., 'iPhone 14 Pro')"
    )
    
    device_model = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="Device model (e.g., 'SM-G998B', 'iPhone14,2')"
    )
    
    os_version = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Operating system version (e.g., 'Android 13', 'iOS 16.5')"
    )
    
    last_refresh_token_jti = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="JTI of last issued refresh token (prevents token replay)"
    )
    
    last_seen = models.DateTimeField(
        auto_now=True,
        help_text="Last time this device authenticated"
    )
    
    is_logged_out = models.BooleanField(
        default=False,
        help_text="Whether this device has been logged out"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="First time this device authenticated"
    )
    
    # Badge system for Flutter app
    is_new = models.BooleanField(
        default=True,
        help_text="Show 'NEW' badge in Flutter app (red dot). Automatically set to True for new devices."
    )
    
    class Meta:
        ordering = ['-last_seen']
        verbose_name = 'Device'
        verbose_name_plural = 'Devices'
        unique_together = [['member', 'device_id']]
        indexes = [
            models.Index(fields=['device_id']),
            models.Index(fields=['member', 'is_logged_out']),
            models.Index(fields=['created_at']),
        ]
    
    def save(self, *args, **kwargs):
        """Normalize and validate device_id before saving"""
        if self.device_id:
            self.device_id = str(self.device_id).strip().lower()
        
        if not self.device_id:
            raise ValueError("device_id cannot be empty")
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        device_info = self.device_name or self.device_model or str(self.device_id)[:8]
        return f"{self.member.user_name}'s {self.platform} ({device_info})"
    
    def logout(self):
        """Mark this device as logged out and clear JTI"""
        self.is_logged_out = True
        self.last_refresh_token_jti = ''
        self.save(update_fields=['is_logged_out', 'last_refresh_token_jti'])


class DeviceToken(models.Model):
    """
    FCM Device Token model for multi-device push notification management.
    
    Features:
    - One user can have multiple device tokens (multi-device support)
    - Each device_id maps to one FCM token
    - Update existing token if same device_id found
    - Remove specific device token on logout
    """
    
    user = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name='device_tokens',
        help_text="Member who owns this device"
    )
    
    device_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Unique device identifier (UUID or device fingerprint)"
    )
    
    fcm_token = models.TextField(
        help_text="Firebase Cloud Messaging token for this device"
    )
    
    platform = models.CharField(
        max_length=20,
        choices=[
            ('android', 'Android'),
            ('ios', 'iOS'),
            ('web', 'Web'),
        ],
        default='android',
        help_text="Device platform"
    )
    
    device_model = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Device model (e.g., 'Pixel 7', 'iPhone 14 Pro')"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this token was first registered"
    )
    
    last_updated = models.DateTimeField(
        auto_now=True,
        help_text="When this token was last updated"
    )
    
    class Meta:
        ordering = ['-last_updated']
        verbose_name = 'Device Token'
        verbose_name_plural = 'Device Tokens'
        unique_together = [['user', 'device_id']]
        indexes = [
            models.Index(fields=['device_id']),
            models.Index(fields=['user', 'device_id']),
            models.Index(fields=['fcm_token']),
        ]
    
    def __str__(self):
        return f"{self.user.user_name}'s {self.platform} device ({self.device_id[:8]}...)"
    
    def save(self, *args, **kwargs):
        """Validate before saving"""
        if not self.device_id or not self.device_id.strip():
            raise ValueError("device_id cannot be empty")
        
        if not self.fcm_token or not self.fcm_token.strip():
            raise ValueError("fcm_token cannot be empty")
        
        # Normalize device_id
        self.device_id = self.device_id.strip().lower()
        self.fcm_token = self.fcm_token.strip()
        
        super().save(*args, **kwargs)
