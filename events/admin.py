from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.http import HttpResponseRedirect
from .models import Event

@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'venue', 'date', 'time_display', 'event_type_badge', 'registration_status_badge', 
        'registration_timeline', 'days_timeline', 'is_today', 'is_new_badge', 'quick_update'
    )
    list_filter = ('event_type', 'registration_status', 'is_new', 'date', 'venue', 'created_at')
    search_fields = ('title', 'description', 'venue')
    ordering = ('-date',)
    date_hierarchy = 'date'
    list_per_page = 20
    readonly_fields = ('event_type', 'registration_status', 'created_at', 'updated_at')
    
    fieldsets = (
        ('📅 Event Information', {
            'fields': ('title', 'description', 'venue', 'is_new'),
            'classes': ('wide',)
        }),
        ('📸 Date, Time & Media', {
            'fields': ('date', 'time', 'image'),
            'classes': ('wide',)
        }),
        ('🔗 Registration Settings', {
            'fields': ('registration_url', 'registration_start_date', 'registration_end_date'),
            'classes': ('wide',),
            'description': 'Set registration dates for upcoming events. Leave blank if no registration required.'
        }),
        ('🤖 Auto-Calculated', {
            'fields': ('event_type', 'registration_status'),
            'classes': ('collapse',),
            'description': 'These fields are automatically calculated.'
        }),
        ('📊 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['update_event_types_action']
    
    def event_type_badge(self, obj):
        """Display event type with colored badge"""
        colors = {
            'upcoming': '#28a745',
            'ongoing': '#fd7e14',
            'past': '#6c757d'
        }
        color = colors.get(obj.event_type, '#007bff')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_event_type_display().upper()
        )
    event_type_badge.short_description = 'Event Status'
    
    def time_display(self, obj):
        """Display formatted time"""
        if obj.time:
            return obj.get_formatted_time()
        return '-'
    time_display.short_description = 'Time'
    
    def registration_status_badge(self, obj):
        """Display registration status with colored badge"""
        colors = {
            'not_started': '#ffc107',  # Yellow
            'open': '#28a745',         # Green
            'closed': '#dc3545',       # Red
            'no_registration': '#6c757d'  # Gray
        }
        color = colors.get(obj.registration_status, '#007bff')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.registration_status_display()
        )
    registration_status_badge.short_description = 'Registration'
    
    def registration_timeline(self, obj):
        """Show registration timeline"""
        if obj.registration_status == 'no_registration':
            return format_html('<span style="color: #6c757d;">➖ No registration</span>')
        elif obj.registration_status == 'not_started':
            timeline = obj.days_until_registration_opens()
            return format_html('<span style="color: #ffc107;">⏳ {}</span>', timeline)
        elif obj.registration_status == 'open':
            timeline = obj.days_until_registration_closes()
            return format_html('<span style="color: #28a745;">✅ {}</span>', timeline)
        elif obj.registration_status == 'closed':
            return format_html('<span style="color: #dc3545;">❌ Registration closed</span>')
        
        return '❓'
    registration_timeline.short_description = 'Registration Timeline'
    
    def days_timeline(self, obj):
        """Show timeline with colors and icons"""
        timeline = obj.days_until_event()
        
        if "TODAY" in timeline:
            return format_html('<strong style="color: #fd7e14; font-size: 12px;">🔥 {}</strong>', timeline)
        elif "In" in timeline:
            return format_html('<span style="color: #28a745; font-weight: bold;">⏰ {}</span>', timeline)
        else:
            return format_html('<span style="color: #6c757d;">📅 {}</span>', timeline)
    days_timeline.short_description = 'Event Timeline'
    
    def quick_update(self, obj):
        """Quick update button for individual events"""
        return format_html(
            '<a href="{}?action=update_single&event_id={}" style="background: #17a2b8; color: white; padding: 2px 6px; border-radius: 3px; text-decoration: none; font-size: 11px;">🔄 Update</a>',
            reverse('admin:events_event_changelist'), obj.id
        )
    quick_update.short_description = 'Actions'
    
    def is_new_badge(self, obj):
        """Display NEW badge with toggle ability"""
        if obj.is_new:
            return format_html(
                '<span style="background: #dc3545; color: white; padding: 3px 6px; border-radius: 10px; font-size: 10px; font-weight: bold;">🔴 NEW</span>'
            )
        return format_html(
            '<span style="color: #6c757d; font-size: 10px;">—</span>'
        )
    is_new_badge.short_description = 'Badge'
    
    def changelist_view(self, request, extra_context=None):
        """Handle quick update action"""
        if request.GET.get('action') == 'update_single':
            event_id = request.GET.get('event_id')
            if event_id:
                try:
                    event = Event.objects.get(id=event_id)
                    old_type = event.event_type
                    event.save()  # This will trigger the auto-update logic in model
                    new_type = event.event_type
                    
                    if old_type != new_type:
                        self.message_user(
                            request, 
                            f'✅ Updated "{event.title}" from {old_type} to {new_type}',
                            level='SUCCESS'
                        )
                    else:
                        self.message_user(
                            request, 
                            f'ℹ️ "{event.title}" is already up to date ({event.event_type})',
                            level='INFO'
                        )
                except Event.DoesNotExist:
                    self.message_user(request, '❌ Event not found', level='ERROR')
                
                return HttpResponseRedirect(reverse('admin:events_event_changelist'))
        
        return super().changelist_view(request, extra_context)
    
    def update_event_types_action(self, request, queryset):
        """Bulk action to update event types for selected events"""
        updated_count = 0
        for event in queryset:
            old_type = event.event_type
            event.save()  # Trigger auto-update
            if old_type != event.event_type:
                updated_count += 1
        
        if updated_count > 0:
            self.message_user(
                request, 
                f'✅ Updated {updated_count} out of {queryset.count()} selected events',
                level='SUCCESS'
            )
        else:
            self.message_user(
                request, 
                f'ℹ️ All {queryset.count()} selected events are already up to date',
                level='INFO'
            )
    update_event_types_action.short_description = "🔄 Update event types based on current date"

# Remove EventRegistrationAdmin completely - we don't need it!

# Customize admin site headers
admin.site.site_header = "🤖 Robotics Club Management System"
admin.site.site_title = "Robotics Club Admin"
admin.site.index_title = "Welcome to Robotics Club Administration Portal"
