# filepath: /home/cks/django projects/robotics_club/notifications/models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from cloudinary.models import CloudinaryField
import logging

logger = logging.getLogger('notifications')


class Notification(models.Model):
    """
    Simple notifications model - just title, description, image, and type
    """
    
    NOTIFICATION_TYPES = [
        ('explore_redirect', 'Explore Redirect'),
        ('open_details', 'Open Details'),
    ]
    
    # Basic notification content
    title = models.CharField(max_length=255)  # Increased from 200 to 255
    description = models.TextField()
    
    # Cloudinary image field - stored in notifications/ folder
    image = CloudinaryField(
        'image',
        folder='notifications',
        blank=True,
        null=True,
        transformation={
            'width': 600,
            'height': 400,
            'crop': 'fill',
            'quality': 'auto',
            'fetch_format': 'auto'
        }
    )
    
    # Notification type
    type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        default='open_details'
    )
    
    # Basic tracking (removed is_read field)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_cloudinary_url(self):
        if self.image:
            return str(self.image.url)
        return None
    
    def get_cloudinary_thumbnail_url(self):
        if self.image:
            from cloudinary import CloudinaryImage
            return CloudinaryImage(str(self.image)).build_url(
                width=200, height=150, crop='fill', quality='auto', fetch_format='auto'
            )
        return None
    
    def __str__(self):
        return f"{self.title} ({self.get_type_display()})"

    class Meta:
        ordering = ['-created_at']

class PushNotification(models.Model):
    """
    Push Notification model for sending FCM push notifications.
    
    Admin creates push notification with title, body, and target (all/specific user).
    When admin clicks 'SEND NOW', the notification is sent via FCM.
    """
    
    SEND_TO_CHOICES = [
        ('all', 'All Users'),
        ('user', 'Specific User'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]
    
    # Notification content
    title = models.CharField(
        max_length=200,
        help_text="Notification title (shown in push notification)"
    )
    
    body = models.TextField(
        help_text="Notification body/message"
    )
    
    # Rich media (required)
    image_url = models.URLField(
        max_length=500,
        blank=False,
        default='https://via.placeholder.com/600x400',
        help_text="Large image URL (shown when notification is expanded - both Android & iOS)"
    )
    
    # Targeting
    send_to = models.CharField(
        max_length=10,
        choices=SEND_TO_CHOICES,
        default='all',
        help_text="Send to all users or specific user"
    )
    
    target_user = models.ForeignKey(
        'authentication.Member',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='push_notifications',
        help_text="Target user (only if send_to='user')"
    )
    
    # Status tracking
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='draft',
        help_text="Notification send status"
    )
    
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When notification was sent"
    )
    
    # Delivery statistics
    devices_targeted = models.IntegerField(
        default=0,
        help_text="Number of devices notification was sent to"
    )
    
    devices_succeeded = models.IntegerField(
        default=0,
        help_text="Number of devices that received notification successfully"
    )
    
    devices_failed = models.IntegerField(
        default=0,
        help_text="Number of devices that failed to receive notification"
    )
    
    error_message = models.TextField(
        blank=True,
        help_text="Error message if sending failed"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    created_by_admin = models.CharField(
        max_length=200,
        blank=True,
        help_text="Admin user who created this notification"
    )
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Push Notification (FCM)'
        verbose_name_plural = 'Push Notifications (FCM)'
    
    def __str__(self):
        target = f"to {self.target_user.user_name}" if self.send_to == 'user' else "to all users"
        return f"{self.title} ({target}) - {self.status}"
    
    def clean(self):
        """Validate that target_user is provided when send_to='user'"""
        if self.send_to == 'user' and not self.target_user:
            raise ValidationError({
                'target_user': 'Target user must be specified when send_to is "user"'
            })
        
        if self.send_to == 'all' and self.target_user:
            raise ValidationError({
                'target_user': 'Target user should not be specified when send_to is "all"'
            })
    
    def save(self, *args, **kwargs):
        """Run validation before saving"""
        self.clean()
        super().save(*args, **kwargs)
    
    def send_notification(self):
        """
        Send this notification via Firebase Cloud Messaging.
        
        This method is called from admin interface when admin clicks 'SEND NOW'.
        It fetches device tokens from Firestore and sends push notification.
        
        Returns:
            dict: Result with success status, message, and statistics
        """
        from authentication import firebase_client_v2
        
        try:
            logger.info(f"Sending push notification: {self.title} ({self.send_to})")
            
            # Get device tokens based on target
            if self.send_to == 'user':
                if not self.target_user:
                    raise ValueError("Target user not specified")
                
                tokens_data = firebase_client_v2.get_tokens_for_user(str(self.target_user.user_id))
                # Add user_id to each token for cleanup
                for token in tokens_data:
                    token['user_id'] = str(self.target_user.user_id)
                
                logger.info(f"Fetched {len(tokens_data)} tokens for user {self.target_user.user_name}")
            else:
                tokens_data = firebase_client_v2.get_all_tokens_batch()
                logger.info(f"Fetched {len(tokens_data)} tokens for all users")
            
            if not tokens_data:
                self.status = 'failed'
                self.error_message = 'No device tokens found for target'
                self.devices_targeted = 0
                self.save()
                
                return {
                    'success': False,
                    'message': 'No device tokens found for target',
                    'devices_targeted': 0,
                    'devices_succeeded': 0,
                    'devices_failed': 0
                }
            
            # Send push notification via FCM (production-ready with retry logic)
            # Ensure image_url is passed correctly (strip whitespace and check if not empty)
            notification_image_url = None
            if self.image_url:
                notification_image_url = self.image_url.strip()
                # Check if it's not the default placeholder
                if notification_image_url and notification_image_url != 'https://via.placeholder.com/600x400':
                    logger.info(f"📷 Sending push notification with image: {notification_image_url}")
                else:
                    logger.warning("⚠️ No valid image URL provided (using placeholder or empty)")
                    notification_image_url = None
            else:
                logger.warning("⚠️ No image_url field set for this notification")
            
            result = firebase_client_v2.send_push_notification_with_retry(
                title=self.title,
                body=self.body,
                tokens_data=tokens_data,
                data={
                    'notification_id': str(self.id),
                    'type': 'push_notification',
                },
                image_url=notification_image_url
            )
            
            # Update notification status
            self.devices_targeted = len(tokens_data)
            self.devices_succeeded = result['success_count']
            self.devices_failed = result['failure_count']
            self.sent_at = timezone.now()
            
            if result['success_count'] > 0:
                self.status = 'sent'
                logger.info(
                    f"Push notification sent: {result['success_count']}/{len(tokens_data)} devices"
                )
            else:
                self.status = 'failed'
                self.error_message = 'All devices failed to receive notification'
                logger.error("All devices failed to receive push notification")
            
            self.save()
            
            # Auto-cleanup invalid tokens (production-ready batch cleanup)
            if result.get('invalid_tokens'):
                logger.info(f"Auto-cleaning up {len(result['invalid_tokens'])} invalid tokens")
                firebase_client_v2.cleanup_invalid_tokens_batch(result['invalid_tokens'])
            
            return {
                'success': result['success_count'] > 0,
                'message': f"Notification sent to {result['success_count']}/{len(tokens_data)} devices",
                'devices_targeted': len(tokens_data),
                'devices_succeeded': result['success_count'],
                'devices_failed': result['failure_count']
            }
            
        except Exception as e:
            logger.error(f"Failed to send push notification: {str(e)}")
            
            self.status = 'failed'
            self.error_message = str(e)
            self.save()
            
            return {
                'success': False,
                'message': f"Failed to send notification: {str(e)}",
                'devices_targeted': 0,
                'devices_succeeded': 0,
                'devices_failed': 0
            }
