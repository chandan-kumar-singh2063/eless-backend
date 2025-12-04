from django.contrib import admin
from django.utils.html import format_html
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import path
from django.conf import settings
import os
from .models import Device, DeviceRequest, AdminAction
from .google_sheets import export_to_google_sheets

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'total_quantity', 'current_available', 'total_booked', 'availability_status')
    search_fields = ('name', 'description')
    readonly_fields = ('current_available', 'total_booked', 'is_available', 'created_at', 'updated_at')
    
    def availability_status(self, obj):
        if obj.is_available:
            return format_html('<span style="color: green;">✅ Available</span>')
        else:
            return format_html('<span style="color: red;">❌ Not Available</span>')
    availability_status.short_description = 'Status'

@admin.register(DeviceRequest)
class DeviceRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'roll_no', 'device', 'requested_quantity', 'request_date', 'admin_status', 'quick_action')
    list_filter = ('request_date', 'device')
    search_fields = ('name', 'roll_no', 'contact', 'device__name', 'user_unique_id')
    readonly_fields = ('request_date', 'created_at', 'updated_at', 'user_unique_id')
    
    # Remove add permission since requests come from Flutter app
    def has_add_permission(self, request):
        return False
    
    def admin_status(self, obj):
        """Show current status with color coding"""
        actions = AdminAction.objects.filter(device_request=obj).order_by('-created_at')
        if actions.exists():
            latest = actions.first()
            if latest.action_type == 'approve':
                if latest.status == 'returned':
                    return format_html('<span style="color: green; font-weight: bold;">✅ Returned</span>')
                elif latest.status == 'overdue':
                    return format_html('<span style="color: red; font-weight: bold;">⚠️ Overdue</span>')
                else:
                    return format_html('<span style="color: blue; font-weight: bold;">✓ Approved ({})</span>', latest.approved_quantity)
            elif latest.action_type == 'reject':
                return format_html('<span style="color: red; font-weight: bold;">✗ Rejected</span>')
        return format_html('<span style="color: orange; font-weight: bold;">⏳ Pending</span>')
    admin_status.short_description = 'Status'
    
    def quick_action(self, obj):
        """Show quick action button for pending requests"""
        actions = AdminAction.objects.filter(device_request=obj)
        if not actions.exists():
            return format_html(
                '<a class="button" href="/admin/services/adminaction/add/?device_request={}" style="background: #417690; color: white; padding: 5px 10px; border-radius: 3px; text-decoration: none;">Take Action</a>',
                obj.id
            )
        return format_html('<span style="color: gray;">Action taken</span>')
    quick_action.short_description = 'Quick Action'
    
    def changelist_view(self, request, extra_context=None):
        """Add export button to the list view"""
        extra_context = extra_context or {}
        
        # Check if Google Sheet URL is configured
        sheet_url = os.getenv('GOOGLE_SHEET_URL', '')
        if sheet_url and sheet_url != 'YOUR_GOOGLE_SHEET_URL_HERE':
            extra_context['show_export_button'] = True
        else:
            extra_context['sheet_url_missing'] = True
        
        return super().changelist_view(request, extra_context)
    
    def get_urls(self):
        """Add custom URL for export"""
        urls = super().get_urls()
        custom_urls = [
            path('export-now/', self.admin_site.admin_view(self.export_now_action), name='devicerequest_export_now'),
        ]
        return custom_urls + urls
    
    def export_now_action(self, request):
        """Handle one-click Google Sheets export"""
        spreadsheet_url = os.getenv('GOOGLE_SHEET_URL', '').strip()
        
        if not spreadsheet_url or spreadsheet_url == 'YOUR_GOOGLE_SHEET_URL_HERE':
            messages.error(
                request, 
                '❌ Google Sheet URL not configured!\n\n'
                'Please add GOOGLE_SHEET_URL to your .env file:\n'
                'GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit\n\n'
                'Then share the sheet with: eless-80@googel-sheet-eless-database.iam.gserviceaccount.com'
            )
        elif 'docs.google.com/spreadsheets' not in spreadsheet_url:
            messages.error(request, '❌ Invalid Google Sheets URL in .env file')
        else:
            try:
                result = export_to_google_sheets(spreadsheet_url)
                
                if result['success']:
                    messages.success(
                        request,
                        f"✅ Successfully exported {result['total_records']} device requests!\n\n"
                        f"📊 New Sheet Created: {result['sheet_title']}\n"
                        f"🕒 Export Time: {result['timestamp']}\n\n"
                        f"Check your Google Sheet now!"
                    )
                else:
                    messages.error(
                        request, 
                        f"❌ Export failed: {result['message']}\n\n"
                        f"Make sure the service account has access to your sheet:\n"
                        f"eless-80@googel-sheet-eless-database.iam.gserviceaccount.com"
                    )
            except Exception as e:
                messages.error(
                    request, 
                    f'❌ Export failed: {str(e)}\n\n'
                    f'Check:\n'
                    f'1. credentials.json exists\n'
                    f'2. Service account has editor access to the sheet\n'
                    f'3. Google Sheets API is enabled'
                )
        
        return HttpResponseRedirect('/admin/services/devicerequest/')

@admin.register(AdminAction)
class AdminActionAdmin(admin.ModelAdmin):
    list_display = ('get_user_name', 'get_device_name', 'get_requested_qty', 'action_type', 'approved_quantity', 'status', 'created_at')
    list_filter = ('action_type', 'status', 'created_at', 'device')
    search_fields = ('device__name', 'device_request__name', 'device_request__roll_no')
    readonly_fields = ('device', 'created_at', 'updated_at', 'get_request_details')
    
    fieldsets = (
        ('📋 Request Details (Read-Only)', {
            'fields': ('get_request_details',),
            'description': 'User and device information from the request'
        }),
        ('✅ Take Action', {
            'fields': ('device_request', 'action_type', 'approved_quantity', 'status'),
            'description': 'Select the request above, then choose your action'
        }),
        ('⏰ Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def get_user_name(self, obj):
        return f"{obj.device_request.name} ({obj.device_request.roll_no})"
    get_user_name.short_description = 'User'
    
    def get_device_name(self, obj):
        return obj.device_request.device.name
    get_device_name.short_description = 'Device'
    
    def get_requested_qty(self, obj):
        return obj.device_request.requested_quantity
    get_requested_qty.short_description = 'Requested Qty'
    
    def get_request_details(self, obj):
        """Show full request details in a nice format"""
        req = obj.device_request
        return format_html(
            '<div style="line-height: 1.8;">'
            '<strong>👤 User:</strong> {} ({})<br>'
            '<strong>📱 Contact:</strong> {}<br>'
            '<strong>🔧 Device:</strong> {}<br>'
            '<strong>📦 Requested Quantity:</strong> {}<br>'
            '<strong>📅 Request Date:</strong> {}<br>'
            '<strong>🎯 Purpose:</strong> {}<br>'
            '<strong>🔄 Return Date:</strong> {}'
            '</div>',
            req.name,
            req.roll_no,
            req.contact,
            req.device.name,
            req.requested_quantity,
            req.request_date.strftime('%d %b %Y'),
            req.purpose or 'Not specified',
            req.expected_return_date.strftime('%d %b %Y') if req.expected_return_date else 'Not specified'
        )
    get_request_details.short_description = 'Request Information'
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Filter device_request to show only pending requests (no actions yet)"""
        if db_field.name == "device_request":
            # Get all device requests that don't have any admin actions yet
            from django.db.models import Count
            pending_requests = DeviceRequest.objects.annotate(
                action_count=Count('adminaction')
            ).filter(action_count=0).order_by('-request_date')
            
            kwargs["queryset"] = pending_requests
            kwargs["help_text"] = "⚠️ Only showing pending requests (no actions taken yet)"
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def save_model(self, request, obj, form, change):
        """Auto-set device from device_request"""
        if obj.device_request:
            obj.device = obj.device_request.device
        super().save_model(request, obj, form, change)

admin.site.site_header = "🤖 Robotics Club - Inventory Management"
admin.site.site_title = "Robotics Club Admin"
admin.site.index_title = "Device & Request Management"

