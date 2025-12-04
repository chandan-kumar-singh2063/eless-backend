from django.urls import path
from . import api_views, fcm_views

app_name = 'notifications'

urlpatterns = [
    # MAIN FLUTTER ENDPOINT - /notifications/api/notifications/
    path('notifications/api/notifications/', api_views.NotificationsListAPIView.as_view(), name='notifications_flutter_list'),
    
    # FCM TOKEN MANAGEMENT - /api/notifications/register-fcm-token/
    path('api/notifications/register-fcm-token/', fcm_views.RegisterFCMTokenView.as_view(), name='register_fcm_token'),
    path('api/notifications/unregister-fcm-token/', fcm_views.UnregisterFCMTokenView.as_view(), name='unregister_fcm_token'),
]