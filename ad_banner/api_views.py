from django.http import JsonResponse
from django.views import View
from .models import AdBanner
import logging

logger = logging.getLogger(__name__)

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.http import JsonResponse
from .models import AdBanner
from urllib.parse import urlparse

class BannerAPIView(APIView):
    """
    API endpoint for Flutter app to get banner advertisements.
    Returns banners in the exact format required by Flutter parsing.
    Public endpoint - no authentication required.
    """
    permission_classes = [AllowAny]
    
    def get(self, request, *args, **kwargs):
        try:
            # Get active banners ordered by their order field
            banners = AdBanner.objects.filter(active=True).order_by('order', '-created_at')
            
            # Get the populate parameter
            populate = request.GET.get('populate', None)
            
            # Build the response data in the exact format Flutter expects
            banner_data = []
            for banner in banners:
                # Get image URL
                image_url = banner.get_cloudinary_url() if banner.image else None
                
                # Create relative path for Flutter baseUrl usage
                relative_path = None
                if image_url:
                    if populate == 'image':
                        # Return full URL when populate=image
                        relative_path = image_url
                    else:
                        # Return relative path for baseUrl usage
                        parsed_url = urlparse(image_url)
                        relative_path = parsed_url.path
                
                # Build banner data in exact Flutter format (Flutter only uses id and image.data.attributes.url)
                banner_item = {
                    "id": banner.id,
                    "attributes": {
                        "image": {
                            "data": {
                                "attributes": {
                                    "url": relative_path
                                }
                            }
                        } if image_url else None
                    }
                }
                
                banner_data.append(banner_item)
            
            # Return the exact structure Flutter expects
            response_data = {
                "data": banner_data
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "data": [],
                "error": f"Error retrieving banners: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
