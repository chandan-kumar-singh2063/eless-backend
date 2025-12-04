from django.urls import path
from . import api_views

app_name = 'events'

urlpatterns = [
    # HOME PAGE APIs - Separate carousels (Original format)
    path('api/ongoing/', api_views.OngoingEventsAPIView.as_view(), name='ongoing_events_api'),
    path('api/upcoming/', api_views.UpcomingEventsAPIView.as_view(), name='upcoming_events_api'),
    path('api/past/', api_views.PastEventsAPIView.as_view(), name='past_events_api'),
    
    # FLUTTER-SPECIFIC APIs - Direct array format
    path('api/flutter/ongoing/', api_views.FlutterOngoingEventsAPIView.as_view(), name='flutter_ongoing_events'),
    path('api/flutter/upcoming/', api_views.FlutterUpcomingEventsAPIView.as_view(), name='flutter_upcoming_events'),
    path('api/flutter/past/', api_views.FlutterPastEventsAPIView.as_view(), name='flutter_past_events'),
    
    # NEW FLUTTER ENDPOINTS FOR EXPLORE SECTION
    path('api/flutter/all/', api_views.FlutterAllEventsAPIView.as_view(), name='flutter_all_events'),
    
    # EXPLORE PAGE API - All events with sort
    path('api/explore/', api_views.ExploreEventsAPIView.as_view(), name='explore_events_api'),
    
    # REGISTRATION STATUS API
    path('api/registrations/', api_views.RegistrationStatusAPIView.as_view(), name='registration_status_api'),
    
    # SINGLE EVENT API
    path('api/events/<int:event_id>/', api_views.EventDetailAPIView.as_view(), name='event_detail_api'),
    
    # STATISTICS API
    path('api/stats/', api_views.EventStatsAPIView.as_view(), name='event_stats_api'),
]