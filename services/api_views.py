from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import models
from django.db.models import Q
from .models import Device, DeviceRequest, AdminAction
import json
from datetime import datetime
import logging
import pytz
from django.utils import timezone

logger = logging.getLogger(__name__)

def format_device_data(device, include_thumbnail=False):
    """Format device data for API response"""
    try:
        # Return relative path for Flutter baseUrl usage (consistent with other apps)
        image_url = None
        if device.image:
            full_url = device.get_cloudinary_url()
            if full_url:
                from urllib.parse import urlparse
                parsed = urlparse(full_url)
                image_url = parsed.path
        
        thumbnail_url = None
        if include_thumbnail and device.image:
            full_thumbnail = device.get_cloudinary_thumbnail_url()
            if full_thumbnail:
                from urllib.parse import urlparse
                parsed = urlparse(full_thumbnail)
                thumbnail_url = parsed.path
        
        return {
            'id': device.id,
            'name': device.name,
            'description': device.description,
            'image_url': image_url,
            'thumbnail_url': thumbnail_url,
            'total_quantity': device.total_quantity,
            'current_available': device.current_available,
            'total_booked': device.total_booked,
            'is_available': device.is_available,
            'availability_text': 'Available' if device.is_available else 'Not Available'
        }
    except Exception as e:
        logger.error(f"Error formatting device data: {str(e)}")
        return None

def format_device_request_data(request_obj):
    """Format device request data (user requests only)"""
    try:
        # Get related admin actions
        admin_actions = AdminAction.objects.filter(device_request=request_obj).order_by('-created_at')
        latest_action = admin_actions.first() if admin_actions.exists() else None
        
        # Determine overall status based on admin actions
        if not admin_actions.exists():
            overall_status = 'pending'
            status_display = 'Pending Review'
        else:
            # Check for return action first (most recent lifecycle stage)
            if latest_action.action_type == 'return':
                overall_status = 'returned'
                status_display = 'Returned'
            elif latest_action.action_type == 'approve':
                # Check the status field for returned/overdue
                if latest_action.status == 'returned':
                    overall_status = 'returned'
                    status_display = 'Returned'
                elif latest_action.status == 'overdue':
                    overall_status = 'overdue'
                    status_display = f'Overdue ({latest_action.approved_quantity})'
                else:
                    overall_status = 'approved'
                    status_display = f'Approved ({latest_action.approved_quantity})'
            elif latest_action.action_type == 'reject':
                overall_status = 'rejected'
                status_display = 'Rejected'
            else:
                overall_status = 'pending'
                status_display = 'Pending Review'
        
        return {
            'id': request_obj.id,
            'device_id': request_obj.device.id,
            'device_name': request_obj.device.name,
            'device_image_url': request_obj.device.get_cloudinary_thumbnail_url(),
            'name': request_obj.name,
            'roll_no': request_obj.roll_no,
            'contact': request_obj.contact,
            'requested_quantity': request_obj.requested_quantity,
            'approved_quantity': latest_action.approved_quantity if latest_action and latest_action.action_type == 'approve' else None,
            'purpose': request_obj.purpose,
            'overall_status': overall_status,
            'status_display': status_display,
            'request_date': request_obj.request_date.strftime('%Y-%m-%d'),
            'expected_return_date': request_obj.expected_return_date.strftime('%Y-%m-%d') if request_obj.expected_return_date else None,
            'is_overdue': latest_action.is_overdue() if latest_action else False,
            'admin_actions_count': admin_actions.count(),
            'created_at': request_obj.created_at.isoformat()
        }
    except Exception as e:
        logger.error(f"Error formatting request data: {str(e)}")
        return None

# 1. SERVICES STATS API
class ServicesStatsAPIView(View):
    """Get overview statistics"""
    
    def get(self, request):
        try:
            # Device stats
            total_devices = Device.objects.count()
            available_devices = Device.objects.filter(is_available=True).count()
            booked_devices = total_devices - available_devices
            total_inventory = Device.objects.aggregate(total=models.Sum('total_quantity'))['total'] or 0
            
            # Request stats - pending requests are those without any admin actions
            all_requests = DeviceRequest.objects.all()
            pending_requests = 0
            for req in all_requests:
                if not AdminAction.objects.filter(device_request=req).exists():
                    pending_requests += 1
            
            # Admin action stats - fix field references
            approved_actions = AdminAction.objects.filter(action_type='approve').exclude(status='returned').count()
            overdue_actions = AdminAction.objects.filter(action_type='approve', status='overdue').count()
            
            stats = {
                'total_devices': total_devices,
                'available_devices': available_devices,
                'booked_devices': booked_devices,
                'total_inventory_items': total_inventory,
                'pending_requests': pending_requests,
                'approved_items': approved_actions,
                'overdue_items': overdue_actions,
            }
            
            return JsonResponse({
                'success': True,
                'stats': stats,
                'message': 'Services statistics fetched successfully'
            })
            
        except Exception as e:
            logger.error(f"Error in ServicesStatsAPIView: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Failed to fetch statistics'}, status=500)

# 2. DEVICES LIST API
class DevicesListAPIView(View):
    """Get all devices with availability"""
    
    def get(self, request):
        try:
            devices = Device.objects.all().order_by('name')
            devices_data = []
            
            for device in devices:
                device.refresh_inventory()
                formatted_data = format_device_data(device, include_thumbnail=True)
                if formatted_data:
                    devices_data.append(formatted_data)
            
            return JsonResponse({
                'success': True,
                'count': len(devices_data),
                'devices': devices_data
            })
            
        except Exception as e:
            logger.error(f"Error in DevicesListAPIView: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Failed to fetch devices'}, status=500)

# 3. DEVICE DETAIL API
class DeviceDetailAPIView(View):
    """Get single device details"""
    
    def get(self, request, device_id):
        try:
            device = Device.objects.get(id=device_id)
            device.refresh_inventory()
            
            device_data = format_device_data(device)
            
            # Get request and action stats - fix field references
            # Count pending requests for this device (those without admin actions)
            device_requests = DeviceRequest.objects.filter(device=device)
            pending_count = 0
            for req in device_requests:
                if not AdminAction.objects.filter(device_request=req).exists():
                    pending_count += 1
            
            device_data.update({
                'pending_requests_count': pending_count,
                'approved_items_count': AdminAction.objects.filter(device=device, action_type='approve').exclude(status='returned').count(),
                'overdue_items_count': AdminAction.objects.filter(device=device, action_type='approve', status='overdue').count(),
                'recent_requests': []
            })
            
            # Get recent requests with their admin actions
            recent_requests = DeviceRequest.objects.filter(device=device).order_by('-request_date')[:5]
            for req in recent_requests:
                request_data = format_device_request_data(req)
                if request_data:
                    device_data['recent_requests'].append(request_data)
            
            return JsonResponse({
                'success': True,
                'device': device_data
            })
            
        except Device.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Device not found'}, status=404)
        except Exception as e:
            logger.error(f"Error in DeviceDetailAPIView: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Failed to fetch device details'}, status=500)

# 5. DEVICE REQUEST SUBMISSION API
@method_decorator(csrf_exempt, name='dispatch')
class DeviceRequestAPIView(View):
    """
    Submit device request (AUDIT FIXED: Atomic operations)
    
    AUDIT FIXES:
    ✅ Uses SELECT FOR UPDATE to prevent race conditions
    ✅ Atomic transaction guarantees no double-booking
    ✅ Proper concurrency handling under load
    """
    
    def post(self, request, device_id):
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['name', 'contact', 'quantity']
            for field in required_fields:
                if field not in data or not data[field]:
                    return JsonResponse({
                        'success': False,
                        'message': f'Missing required field: {field}',
                        'error': 'validation_error',
                        'details': {
                            field: [f'{field} is required']
                        }
                    }, status=400)
            
            # AUDIT FIX: Use atomic function with SELECT FOR UPDATE
            from authentication.atomic_booking import create_device_request_atomic
            success, response_data, status_code = create_device_request_atomic(device_id, data)
            return JsonResponse(response_data, status=status_code)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON format',
                'error': 'json_error'
            }, status=400)
        except Exception as e:
            logger.error(f"Error in DeviceRequestAPIView: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': 'Failed to submit request',
                'error': 'server_error'
            }, status=500)


# 6. USER REQUESTS HISTORY API
class UserRequestsAPIView(View):
    """Get user's request history"""
    
    def get(self, request):
        try:
            roll_no = request.GET.get('roll_no')
            contact = request.GET.get('contact')
            
            if not roll_no and not contact:
                return JsonResponse({'success': False, 'error': 'roll_no or contact required'}, status=400)
            
            # Filter requests
            requests = DeviceRequest.objects.all()
            if roll_no and roll_no != 'N/A':
                requests = requests.filter(roll_no=roll_no)
            elif contact:
                requests = requests.filter(contact=contact)
            
            requests = requests.order_by('-request_date')
            
            requests_data = []
            for req in requests:
                request_data = format_device_request_data(req)
                if request_data:
                    requests_data.append(request_data)
            
            return JsonResponse({
                'success': True,
                'count': len(requests_data),
                'requests': requests_data
            })
            
        except Exception as e:
            logger.error(f"Error in UserRequestsAPIView: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Failed to fetch requests'}, status=500)

# 7. REQUEST STATUS API
class RequestStatusAPIView(View):
    """Check specific request status"""
    
    def get(self, request, request_id):
        try:
            device_request = DeviceRequest.objects.get(id=request_id)
            request_data = format_device_request_data(device_request)
            
            # Get all admin actions for this request
            admin_actions = AdminAction.objects.filter(device_request=device_request).order_by('-created_at')
            actions_data = []
            
            for action in admin_actions:
                actions_data.append({
                    'id': action.id,
                    'action_type': action.action_type,
                    'action_display': action.get_action_type_display(),
                    'approved_quantity': action.approved_quantity,
                    'status': action.status,
                    'status_display': action.get_status_display() if action.status else 'N/A',
                    'created_at': action.created_at.strftime('%Y-%m-%d %H:%M'),
                    'updated_at': action.updated_at.strftime('%Y-%m-%d %H:%M'),
                    'is_overdue': action.is_overdue()
                })
            
            return JsonResponse({
                'success': True,
                'request': request_data,
                'admin_actions': actions_data
            })
            
        except DeviceRequest.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Request not found'}, status=404)
        except Exception as e:
            logger.error(f"Error in RequestStatusAPIView: {str(e)}")
            return JsonResponse({'success': False, 'error': 'Failed to fetch request status'}, status=500)

# 8. ADMIN ACTIONS HISTORY API - Track all admin actions on a request
class AdminActionsAPIView(View):
    """API to get all admin actions for a specific request"""
    
    def get(self, request, request_id):
        try:
            # Verify request exists
            device_request = DeviceRequest.objects.get(id=request_id)
            
            # Get all admin actions for this request
            admin_actions = AdminAction.objects.filter(
                device_request=device_request
            ).order_by('-created_at')
            
            actions_data = []
            for action in admin_actions:
                actions_data.append({
                    'id': action.id,
                    'action_type': action.action_type,
                    'action_display': action.get_action_type_display(),
                    'approved_quantity': action.approved_quantity,
                    'status': action.status,
                    'status_display': action.get_status_display() if action.status else 'N/A',
                    'created_at': action.created_at.strftime('%Y-%m-%d %H:%M'),
                    'updated_at': action.updated_at.strftime('%Y-%m-%d %H:%M'),
                    'is_overdue': action.is_overdue()
                })
            
            return JsonResponse({
                'success': True,
                'request_id': request_id,
                'device_name': device_request.device.name,
                'user_name': device_request.name,
                'roll_no': device_request.roll_no,
                'actions_count': len(actions_data),
                'admin_actions': actions_data,
                'message': f'Found {len(actions_data)} admin actions for request #{request_id}'
            })
            
        except DeviceRequest.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Request not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Error in AdminActionsAPIView: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to fetch admin actions'
            }, status=500)

# 9. PENDING REQUESTS API - For admin dashboard in Flutter
class PendingRequestsAPIView(View):
    """API to get all pending requests for admin review"""
    
    def get(self, request):
        try:
            # Get all requests and filter for those without admin actions (truly pending)
            all_requests = DeviceRequest.objects.all().order_by('-request_date')
            
            requests_data = []
            for req in all_requests:
                # Check if any admin action exists
                has_admin_action = AdminAction.objects.filter(device_request=req).exists()
                
                if not has_admin_action:  # Only truly pending requests
                    request_data = format_device_request_data(req)
                    if request_data:
                        # Add additional admin-relevant info
                        request_data.update({
                            'days_since_request': (timezone.now().date() - req.request_date).days,
                            'device_current_available': req.device.current_available,
                            'device_total_quantity': req.device.total_quantity,
                            'can_approve_full_quantity': req.requested_quantity <= req.device.current_available
                        })
                        requests_data.append(request_data)
            
            return JsonResponse({
                'success': True,
                'count': len(requests_data),
                'pending_requests': requests_data,
                'message': f'Found {len(requests_data)} pending requests awaiting admin action'
            })
            
        except Exception as e:
            logger.error(f"Error in PendingRequestsAPIView: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to fetch pending requests'
            }, status=500)

# 10. OVERDUE ITEMS API - Track overdue returns
class OverdueItemsAPIView(View):
    """API to get all overdue items for admin tracking"""
    
    def get(self, request):
        try:
            # Get all approved actions that are overdue and not returned
            overdue_actions = AdminAction.objects.filter(
                action_type='approve',
                status='overdue'
            ).order_by('-created_at')
            
            overdue_data = []
            for action in overdue_actions:
                nepal_tz = pytz.timezone('Asia/Kathmandu')
                today = timezone.now().astimezone(nepal_tz).date()
                expected_return = action.device_request.expected_return_date
                days_overdue = (today - expected_return).days if expected_return else 0
                
                overdue_data.append({
                    'id': action.id,
                    'device_name': action.device.name,
                    'device_image_url': action.device.get_cloudinary_thumbnail_url(),
                    'user_name': action.device_request.name,
                    'user_contact': action.device_request.contact,
                    'user_roll_no': action.device_request.roll_no,
                    'approved_quantity': action.approved_quantity,
                    'expected_return_date': expected_return.strftime('%Y-%m-%d') if expected_return else None,
                    'days_overdue': days_overdue,
                    'created_at': action.created_at.strftime('%Y-%m-%d')
                })
            
            return JsonResponse({
                'success': True,
                'count': len(overdue_data),
                'overdue_items': overdue_data,
                'message': f'Found {len(overdue_data)} overdue items'
            })
            
        except Exception as e:
            logger.error(f"Error in OverdueItemsAPIView: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to fetch overdue items'
            }, status=500)

# 11. DEVICE AVAILABILITY CHECK API - Before submitting request
class DeviceAvailabilityAPIView(View):
    """API to check real-time device availability before request submission"""
    
    def get(self, request, device_id):
        try:
            device = Device.objects.get(id=device_id)
            device.refresh_inventory()  # Get latest availability
            
            # Get active bookings info (approved actions that are not returned)
            active_bookings = AdminAction.objects.filter(
                device=device,
                action_type='approve'
            ).exclude(status='returned').count()
            
            # Get pending requests count (requests without admin actions)
            device_requests = DeviceRequest.objects.filter(device=device)
            pending_count = 0
            for req in device_requests:
                if not AdminAction.objects.filter(device_request=req).exists():
                    pending_count += 1
            
            # Flutter-compatible response format
            return JsonResponse({
                'is_available': device.is_available,
                'available_quantity': device.current_available,
                'total_quantity': device.total_quantity,
                'message': 'Device is available for request' if device.is_available else 'Device is not available'
            })
            
        except Device.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Device not found',
                'is_available': False,
                'available_quantity': 0,
                'total_quantity': 0,
                'message': 'Device not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Error in DeviceAvailabilityAPIView: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to check device availability',
                'is_available': False,
                'available_quantity': 0,
                'total_quantity': 0,
                'message': 'Failed to check device availability'
            }, status=500)


# ===========================
# FLUTTER-SPECIFIC APIS
# ===========================

def format_device_data_for_flutter(device):
    """Format device data exactly as Flutter expects"""
    try:
        # Refresh inventory to get latest availability
        device.refresh_inventory()
        
        return {
            'id': device.id,
            'name': device.name,
            'description': device.description,
            'image': device.get_cloudinary_url() or '',
            'is_available': device.is_available,
            'total_quantity': device.total_quantity,
            'available_quantity': device.current_available,  # Currently available (not in use)
            'is_new': False  # Add is_new field if you have it in Device model
        }
    except Exception as e:
        logger.error(f"Error formatting device data for Flutter: {str(e)}")
        return None


class FlutterAllDevicesAPIView(View):
    """Flutter-compatible all devices API"""
    
    def get(self, request):
        try:
            devices = Device.objects.all().order_by('name')
            devices_data = []
            
            for device in devices:
                formatted_data = format_device_data_for_flutter(device)
                if formatted_data:
                    devices_data.append(formatted_data)
            
            # Return in Flutter expected format
            return JsonResponse({
                'results': devices_data
            })
        except Exception as e:
            logger.error(f"Error in FlutterAllDevicesAPIView: {str(e)}")
            return JsonResponse({
                'results': []
            })


# SIMPLE CART API - No JWT required, just user_unique_id
from .serializers import UserDeviceRequestSerializer

@method_decorator(csrf_exempt, name='dispatch')
class UserDeviceRequestsView(View):
    """
    Get all device requests for a user (Cart feature).
    
    Endpoint: POST /services/api/user/device-requests/
    Authentication: None (uses user_unique_id from request body)
    
    Body: {
        "user_unique_id": "ROBO-2024-003"
    }
    
    Returns device requests filtered by user_unique_id.
    """
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            user_unique_id = data.get('user_unique_id')
            
            if not user_unique_id:
                return JsonResponse({
                    'success': False,
                    'message': 'user_unique_id is required',
                    'results': []
                }, status=400)
            
            # Query device requests for this user only
            device_requests = DeviceRequest.objects.filter(
                user_unique_id=user_unique_id
            ).select_related('device').order_by('-request_date')
            
            # Serialize the data
            serializer = UserDeviceRequestSerializer(device_requests, many=True)
            
            logger.info(f"Cart loaded: user={user_unique_id}, items={len(serializer.data)}")
            
            return JsonResponse({
                'success': True,
                'results': serializer.data
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON format',
                'results': []
            }, status=400)
        except Exception as e:
            logger.error(f"Error in UserDeviceRequestsView: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': 'Failed to fetch device requests',
                'results': []
            }, status=500)
