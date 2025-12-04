"""
Django Admin Configuration for Authentication App

Provides clean, minimal interfaces for managing Members and Devices.
Focus: Admin creates members with only user_name and user_id fields.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import path
from .models import Member, Device, DeviceToken


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    """
    Admin interface for Member model.
    
    Simplified for easy member creation:
    - Only user_name and user_id visible when creating
    - Clean list view with search and filters
    - No QR code generation (done separately)
    """
    
    # List view configuration
    list_display = [
        'user_id', 
        'user_name', 
        'is_active_badge', 
        'device_count',
        'created_at_formatted'
    ]
    
    list_filter = ['is_active', 'created_at']
    
    search_fields = ['user_name', 'user_id']
    
    # Form configuration - only show essential fields
    fields = ['user_name', 'user_id', 'is_active']
    
    # Read-only fields for editing existing members
    readonly_fields = ['created_at', 'updated_at', 'get_active_devices_info']
    
    # Ordering
    ordering = ['-created_at']
    
    # Limit fields shown when adding new member
    def get_fields(self, request, obj=None):
        """Show minimal fields when creating new member"""
        if obj is None:  # Creating new member
            return ['user_name', 'user_id']
        else:  # Editing existing member
            return [
                'user_name', 
                'user_id', 
                'is_active', 
                'created_at', 
                'updated_at',
                'get_active_devices_info'
            ]
    
    def is_active_badge(self, obj):
        """Display active status as colored badge"""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓ Active</span>'
            )
        return format_html(
            '<span style="color: red; font-weight: bold;">✗ Inactive</span>'
        )
    is_active_badge.short_description = 'Status'
    
    def device_count(self, obj):
        """Display count of active devices"""
        count = obj.get_active_devices().count()
        total = obj.devices.count()
        return f"{count}/{total} active"
    device_count.short_description = 'Devices'
    
    def created_at_formatted(self, obj):
        """Display formatted creation date"""
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_formatted.short_description = 'Created'
    
    def get_active_devices_info(self, obj):
        """Display active devices information in edit view"""
        devices = obj.get_active_devices()
        if not devices:
            return "No active devices"
        
        device_list = "<ul>"
        for device in devices:
            device_list += f"<li>{device.platform}: {device.device_name or str(device.device_id)[:8]}</li>"
        device_list += "</ul>"
        
        return format_html(device_list)
    get_active_devices_info.short_description = 'Active Devices'
    
    # Actions
    actions = ['activate_members', 'deactivate_members']
    
    def activate_members(self, request, queryset):
        """Bulk activate selected members"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} member(s) activated successfully.')
    activate_members.short_description = 'Activate selected members'
    
    def deactivate_members(self, request, queryset):
        """Bulk deactivate selected members"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} member(s) deactivated successfully.')
    deactivate_members.short_description = 'Deactivate selected members'
    
    # Custom admin messages
    def save_model(self, request, obj, form, change):
        """Custom save with user feedback"""
        super().save_model(request, obj, form, change)
        if not change:  # New member created
            self.message_user(
                request, 
                f'Member "{obj.user_name}" created successfully. '
                f'Share user_id "{obj.user_id}" with member for login.',
                level='SUCCESS'
            )


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    """
    Admin interface for Device model.
    
    Read-only view for monitoring device activity.
    Devices are automatically created during QR login.
    """
    
    # List view configuration
    list_display = [
        'get_member_info',
        'platform',
        'device_name_or_id',
        'is_logged_out_badge',
        'is_new_badge',
        'last_seen_formatted',
        'created_at_formatted'
    ]
    
    list_filter = ['platform', 'is_logged_out', 'is_new', 'created_at']
    
    search_fields = ['member__user_name', 'member__user_id', 'device_id', 'device_name']
    
    # Make all fields read-only (devices managed automatically)
    readonly_fields = [
        'member', 'device_id', 'platform', 'device_name',
        'last_refresh_token_jti', 'last_seen', 'is_logged_out', 'is_new', 'created_at'
    ]
    
    # Don't allow adding devices manually
    def has_add_permission(self, request):
        return False
    
    # Allow viewing and deleting only
    def has_change_permission(self, request, obj=None):
        return False
    
    def get_member_info(self, obj):
        """Display member information"""
        return f"{obj.member.user_name} ({obj.member.user_id})"
    get_member_info.short_description = 'Member'
    
    def device_name_or_id(self, obj):
        """Display device name or truncated ID"""
        return obj.device_name or str(obj.device_id)[:13] + '...'
    device_name_or_id.short_description = 'Device'
    
    def is_logged_out_badge(self, obj):
        """Display logout status as badge"""
        if obj.is_logged_out:
            return format_html(
                '<span style="color: red;">Logged Out</span>'
            )
        return format_html(
            '<span style="color: green; font-weight: bold;">Active</span>'
        )
    is_logged_out_badge.short_description = 'Status'
    
    def last_seen_formatted(self, obj):
        """Display formatted last seen date"""
        return obj.last_seen.strftime('%Y-%m-%d %H:%M')
    last_seen_formatted.short_description = 'Last Seen'
    
    def created_at_formatted(self, obj):
        """Display formatted creation date"""
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_formatted.short_description = 'First Seen'
    
    def is_new_badge(self, obj):
        """Display NEW badge for unviewed devices"""
        if obj.is_new:
            return format_html(
                '<span style="background: #dc3545; color: white; padding: 3px 6px; border-radius: 10px; font-size: 10px; font-weight: bold;">🔴 NEW</span>'
            )
        return format_html(
            '<span style="color: #6c757d; font-size: 10px;">—</span>'
        )
    is_new_badge.short_description = 'Badge'
    
    # Actions
    actions = ['logout_devices']
    
    def logout_devices(self, request, queryset):
        """Bulk logout selected devices"""
        for device in queryset:
            device.logout()
        self.message_user(request, f'{queryset.count()} device(s) logged out successfully.')
    logout_devices.short_description = 'Logout selected devices'


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    """
    Admin interface for DeviceToken model.
    
    Shows all registered FCM device tokens with multi-device support.
    """
    
    # List view configuration
    list_display = [
        'user_name_display',
        'device_id_short',
        'platform',
        'device_model',
        'created_at_formatted',
        'last_updated_formatted'
    ]
    
    list_filter = ['platform', 'created_at', 'last_updated']
    
    search_fields = ['user__user_name', 'user__user_id', 'device_id', 'fcm_token']
    
    readonly_fields = ['user', 'device_id', 'fcm_token', 'platform', 'device_model', 'created_at', 'last_updated']
    
    ordering = ['-last_updated']
    
    # Disable adding/editing (tokens are managed via API)
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def user_name_display(self, obj):
        """Display member name and user_id"""
        return f"{obj.user.user_name} ({obj.user.user_id})"
    user_name_display.short_description = 'User'
    
    def device_id_short(self, obj):
        """Display shortened device_id"""
        return f"{obj.device_id[:16]}..." if len(obj.device_id) > 16 else obj.device_id
    device_id_short.short_description = 'Device ID'
    
    def created_at_formatted(self, obj):
        """Display formatted creation date"""
        return obj.created_at.strftime('%Y-%m-%d %H:%M')
    created_at_formatted.short_description = 'Registered'
    
    def last_updated_formatted(self, obj):
        """Display formatted last update date"""
        return obj.last_updated.strftime('%Y-%m-%d %H:%M')
    last_updated_formatted.short_description = 'Last Updated'
    
    # Custom action to send push notification
    actions = ['send_push_notification_action']
    
    def send_push_notification_action(self, request, queryset):
        """Send push notification to selected devices"""
        device_ids = [str(dt.id) for dt in queryset]
        return redirect(f'/admin/authentication/send-push/?devices={",".join(device_ids)}')
    send_push_notification_action.short_description = 'Send push notification to selected'


def send_push_notification_view(request):
    """
    Custom admin view for sending push notifications manually.
    
    Admins can:
    - Send to all users
    - Send to specific users (multi-select)
    - Customize title, body, and data payload
    """
    from .push_notifications import send_to_device, send_to_user, send_to_all, send_to_multiple_users
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        body = request.POST.get('body', '').strip()
        recipient_type = request.POST.get('recipient_type', 'all')
        user_ids = request.POST.getlist('user_ids')
        
        if not title or not body:
            messages.error(request, 'Title and body are required')
            return redirect('/admin/authentication/send-push/')
        
        try:
            if recipient_type == 'all':
                # Send to all devices
                success, total, msg = send_to_all(title, body)
                messages.success(request, f'✅ {msg}')
            
            elif recipient_type == 'selected' and user_ids:
                # Send to selected users
                user_ids_int = [int(uid) for uid in user_ids]
                success, total, msg = send_to_multiple_users(user_ids_int, title, body)
                messages.success(request, f'✅ {msg}')
            
            elif recipient_type == 'single' and user_ids:
                # Send to single user
                member = Member.objects.get(id=int(user_ids[0]))
                success, total, msg = send_to_user(member, title, body)
                messages.success(request, f'✅ {msg}')
            
            else:
                messages.error(request, 'Invalid recipient selection')
        
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
        
        return redirect('/admin/authentication/member/')
    
    # GET request - show form
    context = {
        'title': 'Send Push Notification',
        'members': Member.objects.filter(is_active=True).order_by('user_name'),
        'has_permission': True,
        'site_header': admin.site.site_header,
        'site_title': admin.site.site_title,
    }
    
    return render(request, 'admin/send_push_notification.html', context)


# Customize admin site header
admin.site.site_header = "Robotics Club Admin"
admin.site.site_title = "Robotics Club Admin Portal"
admin.site.index_title = "Welcome to Robotics Club Admin"
