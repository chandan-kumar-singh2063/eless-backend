from django.urls import path
from . import api_views

app_name = 'services'

urlpatterns = [
    # FLUTTER-SPECIFIC APIs (Public access)
    path('api/flutter/all/', api_views.FlutterAllDevicesAPIView.as_view(), name='flutter_all_devices'),
    
    # SERVICES HOME PAGE API - Stats for home containers
    path('api/stats/', api_views.ServicesStatsAPIView.as_view(), name='services_stats_api'),
    
    # DEVICES APIs - Grid view and availability
    path('api/devices/', api_views.DevicesListAPIView.as_view(), name='devices_list_api'),
    path('api/devices/<int:device_id>/', api_views.DeviceDetailAPIView.as_view(), name='device_detail_api'),
    path('api/devices/<int:device_id>/availability/', api_views.DeviceAvailabilityAPIView.as_view(), name='device_availability_api'),  # NEW
    
    # DEVICE REQUEST APIs - Submit and track requests
    path('api/devices/<int:device_id>/request/', api_views.DeviceRequestAPIView.as_view(), name='device_request_api'),
    
    # USER REQUEST HISTORY APIs - Track user's requests
    path('api/requests/', api_views.UserRequestsAPIView.as_view(), name='user_requests_api'),
    path('api/requests/<int:request_id>/', api_views.RequestStatusAPIView.as_view(), name='request_status_api'),
    path('api/requests/<int:request_id>/actions/', api_views.AdminActionsAPIView.as_view(), name='admin_actions_api'),  # NEW
    
    # ADMIN DASHBOARD APIs - For admin features in Flutter
    path('api/admin/pending-requests/', api_views.PendingRequestsAPIView.as_view(), name='pending_requests_api'),  # NEW
    path('api/admin/overdue-items/', api_views.OverdueItemsAPIView.as_view(), name='overdue_items_api'),  # NEW
    
    # CART API - JWT-protected user-specific device requests
    path('api/user/device-requests/', api_views.UserDeviceRequestsView.as_view(), name='user_device_requests'),  # NEW
]