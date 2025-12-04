from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .models import Notification
import logging

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
    GET /api/notifications/ - List All Notifications (READ-ONLY)
    
    Returns all notifications for Flutter app.
    Flutter handles read/unread status locally using Hive storage.
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        try:
            notifications = Notification.objects.all().order_by('-created_at')
            
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