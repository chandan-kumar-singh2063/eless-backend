"""
FCM Token Management API Views

Separate endpoints for FCM token registration/unregistration.
Uses ONLY Firestore (no PostgreSQL) to save Supabase free tier.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from .fcm_serializers import RegisterFCMTokenSerializer, UnregisterFCMTokenSerializer
import logging

logger = logging.getLogger('notifications')


class RegisterFCMTokenView(APIView):
    """
    Register FCM Token for Push Notifications
    
    POST /api/notifications/register-fcm-token/
    
    Authentication: Not Required (Public endpoint for seamless registration after QR login)
    
    Storage: ONLY Firestore (no PostgreSQL)
    
    Request Body:
        {
            "user_unique_id": "ROBO-2024-001",
            "fcm_token": "fPida7AGSe6...",
            "device_id": "772dd712-480e-4305...",
            "platform": "android",
            "device_model": "Pixel 6",
            "device_manufacturer": "Google"
        }
    
    Response:
        {
            "success": true,
            "message": "FCM token registered successfully",
            "device_id": "772dd712-480e-4305...",
            "storage": "firestore"
        }
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    
    def post(self, request):
        logger.info(f"🔔 FCM token registration request from user: {request.user}")
        
        serializer = RegisterFCMTokenSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.warning(f"❌ FCM token registration validation failed: {serializer.errors}")
            return Response(
                {
                    'success': False,
                    'error': 'Invalid request data',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        user_unique_id = validated_data['user_unique_id']
        fcm_token = validated_data['fcm_token']
        device_id = validated_data['device_id']
        platform = validated_data.get('platform', 'unknown')
        device_model = validated_data.get('device_model', '')
        device_manufacturer = validated_data.get('device_manufacturer', '')
        
        try:
            # Save ONLY to Firestore (no PostgreSQL)
            from authentication import firebase_client_v2
            
            success = firebase_client_v2.save_device_token(
                user_id=user_unique_id,
                device_id=device_id,
                fcm_token=fcm_token,
                platform=platform,
                device_model=device_model
            )
            
            if not success:
                raise Exception("Firestore save failed")
            
            logger.info(
                f"✅ FCM token registered in Firestore: user={user_unique_id}, "
                f"device={device_id[:12]}..., platform={platform}"
            )
            
            return Response(
                {
                    'success': True,
                    'message': 'FCM token registered successfully',
                    'device_id': device_id,
                    'storage': 'firestore'
                },
                status=status.HTTP_201_CREATED
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to register FCM token: {str(e)}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'error': 'Failed to register FCM token'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UnregisterFCMTokenView(APIView):
    """
    Unregister FCM Token on Logout
    
    POST /api/notifications/unregister-fcm-token/
    
    Authentication: Not Required (Public endpoint for seamless unregistration on logout)
    
    Storage: ONLY Firestore (no PostgreSQL)
    
    Request Body:
        {
            "user_unique_id": "ROBO-2024-001",
            "device_id": "772dd712-480e..."
        }
    
    Response:
        {
            "success": true,
            "message": "FCM token unregistered successfully"
        }
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    
    def post(self, request):
        logger.info(f"🚪 FCM token unregistration request from user: {request.user}")
        
        user_unique_id = request.data.get('user_unique_id')
        device_id = request.data.get('device_id')
        
        if not user_unique_id or not device_id:
            return Response(
                {
                    'success': False,
                    'error': 'user_unique_id and device_id are required'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Remove ONLY from Firestore (no PostgreSQL)
            from authentication import firebase_client_v2
            
            success = firebase_client_v2.delete_device_token(
                user_id=user_unique_id,
                device_id=device_id
            )
            
            logger.info(f"✅ FCM token unregistered from Firestore: device={device_id[:12]}...")
            
            return Response(
                {
                    'success': True,
                    'message': 'FCM token unregistered successfully',
                    'storage': 'firestore'
                },
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to unregister FCM token: {str(e)}", exc_info=True)
            return Response(
                {
                    'success': False,
                    'error': 'Failed to unregister FCM token'
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
