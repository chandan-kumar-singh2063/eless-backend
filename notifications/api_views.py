from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .models import Notification
import logging
from robotics_club.pagination import paginate_queryset
from django.http import JsonResponse

logger = logging.getLogger(__name__)

def format_notification_for_flutter(notification):
    """
    Format notification data for Flutter app requirements
    Handles both explore_redirect and open_details types
    """
    try:
        # Get image URL - return relative path for Flutter baseUrl usage
        image_url = ""  # Default empty string as per requirements
        if notification.image:
            full_url = notification.get_cloudinary_url()
            if full_url:
                # Extract relative path from full Cloudinary URL
                from urllib.parse import urlparse
                parsed = urlparse(full_url)
                image_url = parsed.path
        
        return {
            'id': notification.id,
            'title': notification.title,
            'description': notification.description,  # Can be empty for explore_redirect
            'image': image_url,  # Can be empty string
            'type': notification.type,
            'created_at': notification.created_at.strftime('%Y-%m-%dT%H:%M:%SZ')
        }
    except Exception as e:
        logger.error(f"Error formatting notification: {str(e)}")
        return None


class NotificationsListAPIView(APIView):
    """
    GET /api/notifications/ - List All Notifications with Pagination Support
    
    Returns notifications for Flutter app with pagination.
    Flutter handles read/unread status locally using Hive storage.
    
    Query Parameters:
        - page: Page number (default: 1)
        - page_size: Items per page (default: 15, max: 50)
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        try:
            notifications = Notification.objects.all().order_by('-created_at')
            
            # Check if pagination is requested
            page_param = request.GET.get('page')
            
            if page_param:
                # PAGINATED RESPONSE
                paginated_data = paginate_queryset(
                    request,
                    notifications,
                    default_page_size=15,
                    max_page_size=50
                )
                
                # Serialize results
                results = []
                for notification in paginated_data['results']:
                    notification_data = format_notification_for_flutter(notification)
                    if notification_data:
                        results.append(notification_data)
                
                return Response({
                    'results': results,
                    'next': paginated_data['next'],
                    'previous': paginated_data['previous'],
                    'count': paginated_data['count'],
                    'page': paginated_data['page'],
                    'total_pages': paginated_data['total_pages']
                }, status=status.HTTP_200_OK)
            else:
                # NON-PAGINATED RESPONSE - Backward compatibility
                results = []
                for notification in notifications:
                    notification_data = format_notification_for_flutter(notification)
                    if notification_data:
                        results.append(notification_data)
                
                return Response({
                    'results': results
                }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error in NotificationsListAPIView: {str(e)}")
            return Response({
                'error': 'Failed to fetch notifications'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)