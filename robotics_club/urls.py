from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from authentication.admin import send_push_notification_view

urlpatterns = [
    path('admin/', admin.site.urls),
    # Custom admin view for sending push notifications
    path('admin/authentication/send-push/', admin.site.admin_view(send_push_notification_view), name='admin_send_push'),
    # Authentication API
    path('api/auth/', include('authentication.urls')),
    # Notifications API
    path('', include('notifications.urls')),
    # Other APIs
    path('events/', include('events.urls')),
    path('services/', include('services.urls')),
    path('', include('ad_banner.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
