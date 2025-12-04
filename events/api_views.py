from django.http import JsonResponse
from django.db.models import Q
from django.views import View
from .models import Event
import json
import logging

logger = logging.getLogger(__name__)

def format_event_data(event):
    """Helper function to format event data for API response"""
    try:
        # Return relative path for Flutter baseUrl usage (consistent with other apps)
        image_url = None
        if event.image:
            image_path = str(event.image.url)
            if image_path.startswith('http'):
                # Extract relative path from full URL
                from urllib.parse import urlparse
                parsed = urlparse(image_path)
                image_url = parsed.path
            else:
                image_url = image_path
        
        return {
            'id': event.id,
            'title': event.title,
            'description': event.description,
            'venue': event.venue,
            'date': event.date.strftime('%Y-%m-%d'),
            'event_type': event.event_type,
            'event_type_display': event.get_event_type_display(),
            'image_url': image_url,
            'days_until_event': event.days_until_event(),
            'is_today': event.is_today(),
            'cloudinary_folder': event.get_cloudinary_folder(),
            
            # Registration Information
            'registration_url': event.registration_url,
            'registration_start_date': event.registration_start_date.strftime('%Y-%m-%d') if event.registration_start_date else None,
            'registration_end_date': event.registration_end_date.strftime('%Y-%m-%d') if event.registration_end_date else None,
            'registration_status': event.registration_status,
            'registration_status_display': event.registration_status_display(),
            'is_registration_open': event.is_registration_open(),
            'days_until_registration_opens': event.days_until_registration_opens(),
            'days_until_registration_closes': event.days_until_registration_closes(),
            
            # CRITICAL FIX (Bug #11): Add timestamp fields
            'created_at': event.created_at.isoformat() if hasattr(event, 'created_at') and event.created_at else None,
            'updated_at': event.updated_at.isoformat() if hasattr(event, 'updated_at') and event.updated_at else None,
            
            # Badge system: Show NEW badge in Flutter app
            'is_new': event.is_new if hasattr(event, 'is_new') else False,
        }
    except Exception as e:
        logger.error(f"Error formatting event data for event {event.id}: {str(e)}")
        return None

def format_event_data_for_flutter(event):
    """Format event data specifically for Flutter app compatibility"""
    try:
        # Get relative image path for Flutter baseUrl usage
        image_path = None
        if event.image:
            if hasattr(event.image, 'url'):
                # For Cloudinary or regular ImageField
                image_path = str(event.image.url)
                # Convert to relative path if it's a full URL
                if image_path.startswith('http'):
                    # Extract the path part for relative usage
                    from urllib.parse import urlparse
                    parsed = urlparse(image_path)
                    image_path = parsed.path
            else:
                image_path = str(event.image)
        
        return {
            "id": event.id,
            "title": event.title,
            "description": event.description,
            "image": image_path,  # Relative path for baseUrl usage
            "date": event.date.strftime('%Y-%m-%d'),  # YYYY-MM-DD format
            "time": event.get_formatted_time(),  # "10:00 AM" format or None
            "location": event.venue,  # Renamed from venue to location for Flutter
            "registration_status": event.registration_status,  # 'open', 'closed', 'no_registration'
            "registration_url": event.registration_url,  # Include registration URL
            
            # CRITICAL FIX (Bug #11): Add timestamp fields
            "created_at": event.created_at.isoformat() if hasattr(event, 'created_at') and event.created_at else None,
            "updated_at": event.updated_at.isoformat() if hasattr(event, 'updated_at') and event.updated_at else None,
            
            # Badge system: Show NEW badge in Flutter app
            "is_new": event.is_new if hasattr(event, 'is_new') else False,
        }
    except Exception as e:
        logger.error(f"Error formatting Flutter event data for event {event.id}: {str(e)}")
        return None

# 1. HOME PAGE APIs - Separate carousels for ongoing, upcoming, past
class OngoingEventsAPIView(View):
    """API for ongoing events carousel on home page"""
    
    def get(self, request):
        try:
            # Only return active events
            events = Event.objects.filter(event_type='ongoing', is_active=True).order_by('date')
            events_data = []
            
            for event in events:
                formatted_data = format_event_data(event)
                if formatted_data:
                    events_data.append(formatted_data)
            
            return JsonResponse({
                'success': True,
                'count': len(events_data),
                'events': events_data,
                'type': 'ongoing'
            })
        except Exception as e:
            logger.error(f"Error in OngoingEventsAPIView: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to fetch ongoing events'
            }, status=500)

class UpcomingEventsAPIView(View):
    """API for upcoming events carousel on home page"""
    
    def get(self, request):
        try:
            # Only return active events
            events = Event.objects.filter(event_type='upcoming', is_active=True).order_by('date')[:10]  # Limit for carousel
            events_data = [format_event_data(event) for event in events]
            
            return JsonResponse({
                'success': True,
                'count': len(events_data),
                'events': events_data,
                'type': 'upcoming'
            })
        except Exception as e:
            logger.error(f"Error in UpcomingEventsAPIView: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to fetch upcoming events'
            }, status=500)

class PastEventsAPIView(View):
    """API for past events carousel on home page"""
    
    def get(self, request):
        try:
            # Only return active events
            events = Event.objects.filter(event_type='past', is_active=True).order_by('-date')[:10]  # Limit for carousel
            events_data = [format_event_data(event) for event in events]
            
            return JsonResponse({
                'success': True,
                'count': len(events_data),
                'events': events_data,
                'type': 'past'
            })
        except Exception as e:
            logger.error(f"Error in PastEventsAPIView: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to fetch past events'
            }, status=500)

# FLUTTER-SPECIFIC API ENDPOINTS - Return exact format Flutter expects
class FlutterOngoingEventsAPIView(View):
    """Flutter-compatible ongoing events API - Returns array directly"""
    
    def get(self, request):
        try:
            events = Event.objects.filter(event_type='ongoing').order_by('-created_at')
            events_data = []
            
            for event in events:
                formatted_data = format_event_data_for_flutter(event)
                if formatted_data:
                    events_data.append(formatted_data)
            
            # Return array directly as Flutter expects
            return JsonResponse(events_data, safe=False)
        except Exception as e:
            logger.error(f"Error in FlutterOngoingEventsAPIView: {str(e)}")
            return JsonResponse([], safe=False)

class FlutterUpcomingEventsAPIView(View):
    """Flutter-compatible upcoming events API - Returns array directly"""
    
    def get(self, request):
        try:
            events = Event.objects.filter(event_type='upcoming').order_by('date')  # Earliest first
            events_data = []
            
            for event in events:
                formatted_data = format_event_data_for_flutter(event)
                if formatted_data:
                    events_data.append(formatted_data)
            
            # Return array directly as Flutter expects
            return JsonResponse(events_data, safe=False)
        except Exception as e:
            logger.error(f"Error in FlutterUpcomingEventsAPIView: {str(e)}")
            return JsonResponse([], safe=False)

class FlutterPastEventsAPIView(View):
    """Flutter-compatible past events API - Returns array directly"""
    
    def get(self, request):
        try:
            events = Event.objects.filter(event_type='past').order_by('-date')  # Most recent first
            events_data = []
            
            for event in events:
                formatted_data = format_event_data_for_flutter(event)
                if formatted_data:
                    events_data.append(formatted_data)
            
            # Return array directly as Flutter expects
            return JsonResponse(events_data, safe=False)
        except Exception as e:
            logger.error(f"Error in FlutterPastEventsAPIView: {str(e)}")
            return JsonResponse([], safe=False)

# NEW FLUTTER ENDPOINTS FOR EXPLORE SECTION
class FlutterAllEventsAPIView(View):
    """Flutter-compatible all events API - Returns categorized events"""
    
    def get(self, request):
        try:
            # Get events by category
            ongoing_events = Event.objects.filter(event_type='ongoing').order_by('-created_at')
            upcoming_events = Event.objects.filter(event_type='upcoming').order_by('date')
            past_events = Event.objects.filter(event_type='past').order_by('-date')
            
            # Format data for each category
            ongoing_data = []
            for event in ongoing_events:
                formatted_data = format_event_data_for_flutter(event)
                if formatted_data:
                    ongoing_data.append(formatted_data)
            
            upcoming_data = []
            for event in upcoming_events:
                formatted_data = format_event_data_for_flutter(event)
                if formatted_data:
                    upcoming_data.append(formatted_data)
            
            past_data = []
            for event in past_events:
                formatted_data = format_event_data_for_flutter(event)
                if formatted_data:
                    past_data.append(formatted_data)
            
            # Return categorized data directly - no success wrapper
            return JsonResponse({
                "ongoing": ongoing_data,
                "upcoming": upcoming_data,
                "past": past_data
            })
        except Exception as e:
            logger.error(f"Error in FlutterAllEventsAPIView: {str(e)}")
            return JsonResponse({
                "ongoing": [],
                "upcoming": [],
                "past": []
            })

# 2. EXPLORE PAGE API - All events with sort
class ExploreEventsAPIView(View):
    """API for explore page with sort functionality"""
    
    def get(self, request):
        try:
            # Get query parameters
            sort_by = request.GET.get('sort', 'newest')  # 'newest' or 'oldest'
            event_type = request.GET.get('type', 'all')  # Filter by type if needed
            page = int(request.GET.get('page', 1))
            per_page = int(request.GET.get('per_page', 20))
            
            # Start with all events
            events = Event.objects.all()
            
            # Apply event type filter
            if event_type != 'all':
                events = events.filter(event_type=event_type)
            
            # Apply sorting
            if sort_by == 'oldest':
                events = events.order_by('date')  # Oldest date first
            else:  # Default to newest
                events = events.order_by('-date')  # Newest date first
            
            # Calculate pagination
            total_count = events.count()
            start = (page - 1) * per_page
            end = start + per_page
            events_page = events[start:end]
            
            # Convert to JSON format
            events_data = [format_event_data(event) for event in events_page]
            
            return JsonResponse({
                'success': True,
                'count': len(events_data),
                'total_count': total_count,
                'page': page,
                'per_page': per_page,
                'has_more': end < total_count,
                'events': events_data,
                'filters': {
                    'sort': sort_by,
                    'type': event_type
                }
            })
        except Exception as e:
            logger.error(f"Error in ExploreEventsAPIView: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to fetch events'
            }, status=500)

# 3. REGISTRATION STATUS API - For upcoming events
class RegistrationStatusAPIView(View):
    """API to get registration status for upcoming events"""
    
    def get(self, request):
        try:
            upcoming_events = Event.objects.filter(event_type='upcoming').order_by('date')
            
            registration_data = []
            for event in upcoming_events:
                registration_info = {
                    'id': event.id,
                    'title': event.title,
                    'date': event.date.strftime('%Y-%m-%d'),
                    'registration_status': event.registration_status,
                    'registration_status_display': event.registration_status_display(),
                    'is_registration_open': event.is_registration_open(),
                    'registration_url': event.registration_url if event.is_registration_open() else None,
                    'days_until_registration_opens': event.days_until_registration_opens(),
                    'days_until_registration_closes': event.days_until_registration_closes(),
                    'registration_start_date': event.registration_start_date.strftime('%Y-%m-%d') if event.registration_start_date else None,
                    'registration_end_date': event.registration_end_date.strftime('%Y-%m-%d') if event.registration_end_date else None,
                }
                registration_data.append(registration_info)
            
            return JsonResponse({
                'success': True,
                'count': len(registration_data),
                'registrations': registration_data
            })
        except Exception as e:
            logger.error(f"Error in RegistrationStatusAPIView: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to fetch registration statuses'
            }, status=500)

# 4. SINGLE EVENT API
class EventDetailAPIView(View):
    """API endpoint to get single event details"""
    
    def get(self, request, event_id):
        try:
            event = Event.objects.get(id=event_id)
            event_data = format_event_data(event)
            
            return JsonResponse({
                'success': True,
                'event': event_data
            })
            
        except Event.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Event not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Error in EventDetailAPIView: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to fetch event details'
            }, status=500)

# 5. STATISTICS API - For home page overview
class EventStatsAPIView(View):
    """API to get event statistics for home page"""
    
    def get(self, request):
        try:
            stats = {
                'total_events': Event.objects.count(),
                'upcoming_events': Event.objects.filter(event_type='upcoming').count(),
                'ongoing_events': Event.objects.filter(event_type='ongoing').count(),
                'past_events': Event.objects.filter(event_type='past').count(),
                'open_registrations': Event.objects.filter(registration_status='open').count(),
            }
            
            return JsonResponse({
                'success': True,
                'stats': stats
            })
        except Exception as e:
            logger.error(f"Error in EventStatsAPIView: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to fetch event statistics'
            }, status=500)