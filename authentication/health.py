"""
Health Check and Metrics Endpoints

AUDIT FIXES:
✅ Health check endpoint for monitoring
✅ Metrics endpoint for push notifications
✅ Database connectivity check
✅ Firebase connectivity check
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from django.db import connection
from django.utils import timezone
import logging

from . import firebase_client_v2

logger = logging.getLogger('authentication')


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring
    
    GET /api/auth/health/
    
    Returns:
        - status: "healthy" or "unhealthy"
        - timestamp: Current server time
        - checks: Individual service checks
    """
    checks = {}
    overall_healthy = True
    
    # Check database connectivity
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks['database'] = 'healthy'
    except Exception as e:
        checks['database'] = f'unhealthy: {str(e)}'
        overall_healthy = False
    
    # Check Firebase connectivity
    try:
        firebase_client_v2.get_firestore_client()
        checks['firebase'] = 'healthy'
    except Exception as e:
        checks['firebase'] = f'unhealthy: {str(e)}'
        overall_healthy = False
    
    return Response({
        'status': 'healthy' if overall_healthy else 'unhealthy',
        'timestamp': timezone.now().isoformat(),
        'checks': checks,
    }, status=status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE)


@api_view(['GET'])
@permission_classes([AllowAny])
def metrics_view(request):
    """
    Get push notification metrics
    
    GET /api/auth/metrics/
    
    Returns metrics for monitoring dashboard
    """
    metrics = firebase_client_v2.get_push_metrics()
    
    return Response({
        'metrics': metrics,
        'timestamp': timezone.now().isoformat(),
    })
