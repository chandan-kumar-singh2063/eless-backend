"""
URL Configuration for Authentication API

Defines endpoints for QR login, token refresh, logout, profile, and device token management.
"""

from django.urls import path
from . import views, health

app_name = 'authentication'

urlpatterns = [
    # QR Code Login
    path('qr-login/', views.qr_login, name='qr_login'),
    
    # Token Refresh (with rotation and blacklisting)
    path('token/refresh/', views.token_refresh, name='token_refresh'),
    
    # Logout (blacklist refresh token)
    path('logout/', views.logout, name='logout'),
    
    # Protected Profile Endpoint
    path('profile/', views.profile, name='profile'),
    
    # Device Token Management (FCM - Legacy Firestore)
    path('device/save-token/', views.save_device_token, name='save_device_token'),
    path('device/remove-token/', views.remove_device_token, name='remove_device_token'),
    
    # Device Token Management (NEW - Multi-Device Support)
    path('register-device/', views.register_device, name='register_device'),
    path('unregister-device/', views.unregister_device, name='unregister_device'),
    
    # Health Check & Monitoring
    path('health/', health.health_check, name='health_check'),
    path('metrics/', health.metrics_view, name='metrics'),
]
