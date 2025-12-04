from django.contrib import admin
from django.utils.html import format_html
from .models import AdBanner

@admin.register(AdBanner)
class AdBannerAdmin(admin.ModelAdmin):
    list_display = ('banner_id', 'banner_preview', 'active', 'order', 'created_at')
    list_editable = ('active', 'order')
    list_filter = ('active', 'created_at', 'updated_at')
    search_fields = ('id',)
    ordering = ['order', '-created_at']
    readonly_fields = ('created_at', 'updated_at', 'banner_preview_large')
    
    fieldsets = (
        ('Banner Information', {
            'fields': ('image',),
            'description': 'Upload banner image - Flutter app only displays the image (no title/description)'
        }),
        ('Display Settings', {
            'fields': ('active', 'order')
        }),
        ('Preview', {
            'fields': ('banner_preview_large',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    
    def banner_id(self, obj):
        """Display banner ID"""
        return f"Banner #{obj.id}"
    banner_id.short_description = 'ID'
    
    def banner_preview(self, obj):
        """Small preview for list view"""
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 100px; height: auto; border-radius: 4px;" />',
                obj.get_cloudinary_url()
            )
        return "No Image"
    banner_preview.short_description = 'Preview'
    
    def banner_preview_large(self, obj):
        """Large preview for detail view"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 400px; height: auto; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />',
                obj.get_cloudinary_url()
            )
        return "No Image Available"
    banner_preview_large.short_description = 'Banner Preview'
    
    def get_queryset(self, request):
        """Order by display order and creation date"""
        return super().get_queryset(request).order_by('order', '-created_at')

# Customize admin site headers
admin.site.site_header = "CKS - ELESS"
admin.site.site_title = "Banner Admin"
admin.site.index_title = "Advertisement Banner Management"
