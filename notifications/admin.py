from django.contrib import admin
from django.contrib import messages
from django.urls import path
from django.shortcuts import render, redirect
from django.utils.html import format_html
from .models import Notification, PushNotification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'type', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('title', 'description')
    
    fieldsets = (
        ('Notification Content', {
            'fields': ('title', 'description', 'image', 'type')
        }),
        ('Notification Behavior', {
            'description': (
                'Type determines Flutter behavior:<br>'
                '• <strong>explore_redirect</strong>: Opens explore screen (description can be empty)<br>'
                '• <strong>open_details</strong>: Shows notification details (description required)'
            ),
            'fields': ()
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PushNotification)
class PushNotificationAdmin(admin.ModelAdmin):
    """
    Admin interface for Push Notifications (FCM).
    
    Provides custom "SEND NOW" button to send notifications immediately.
    """
    
    list_display = (
        'title',
        'send_to',
        'target_user',
        'status',
        'devices_succeeded',
        'devices_failed',
        'sent_at',
        'send_button'
    )
    
    list_filter = ('status', 'send_to', 'created_at')
    search_fields = ('title', 'body', 'target_user__user_name')
    
    readonly_fields = (
        'status',
        'sent_at',
        'devices_targeted',
        'devices_succeeded',
        'devices_failed',
        'error_message',
        'created_at',
        'updated_at'
    )
    
    fieldsets = (
        ('Notification Content', {
            'fields': ('title', 'body')
        }),
        ('Rich Media (REQUIRED)', {
            'fields': ('image_url',),
            'description': (
                '<strong>Image URL (Required)</strong>: Large image shown when notification is expanded (works on both Android & iOS)<br>'
                'Use Cloudinary URLs or any publicly accessible HTTPS image URL<br>'
                '<em>When clicked, notification opens the app normally (home screen)</em>'
            ),
        }),
        ('Targeting', {
            'fields': ('send_to', 'target_user'),
            'description': 'Choose whether to send to all users or a specific user'
        }),
        ('Status & Statistics', {
            'fields': (
                'status',
                'sent_at',
                'devices_targeted',
                'devices_succeeded',
                'devices_failed',
                'error_message'
            ),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by_admin', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def send_button(self, obj):
        """Display SEND NOW button in list view - Always allow resending"""
        if obj.pk:
            button_text = "SEND NOW" if obj.status == 'draft' else "RESEND"
            button_style = 'background-color: #417690; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none; display: inline-block;'
            
            return format_html(
                '<a class="button" style="{}" href="{}">{}</a>',
                button_style,
                f'/admin/notifications/pushnotification/{obj.pk}/send/',
                button_text
            )
        return '-'
    
    send_button.short_description = 'Action'
    
    def get_urls(self):
        """Add custom URL for sending notification"""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:notification_id>/send/',
                self.admin_site.admin_view(self.send_notification_view),
                name='notifications_pushnotification_send',
            ),
        ]
        return custom_urls + urls
    
    def send_notification_view(self, request, notification_id):
        """Custom view to handle sending notification - Allow resending"""
        notification = PushNotification.objects.get(pk=notification_id)
        
        # Reset status to draft before resending (allows multiple sends)
        notification.status = 'draft'
        notification.error_message = ''
        notification.save()
        
        # Send the notification
        result = notification.send_notification()
        
        # Show result message to admin
        if result['success']:
            messages.success(
                request,
                f"✓ Notification sent successfully to {result['devices_succeeded']} "
                f"device(s). {result['devices_failed']} failed."
            )
        else:
            messages.error(
                request,
                f"✗ Failed to send notification: {result['message']}"
            )
        
        # Redirect back to notification detail page
        return redirect(f'/admin/notifications/pushnotification/{notification_id}/change/')
    
    def save_model(self, request, obj, form, change):
        """Save admin username who created the notification"""
        if not change:
            obj.created_by_admin = request.user.username
        super().save_model(request, obj, form, change)
