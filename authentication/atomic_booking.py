"""
Atomic Booking Service with Concurrency Protection

AUDIT FIXES:
✅ SELECT FOR UPDATE prevents race conditions
✅ Atomic transactions
✅ Double-booking prevention
✅ Proper error handling
"""

from django.db import transaction
from django.http import JsonResponse
from services.models import Device, DeviceRequest, AdminAction
from datetime import datetime
import logging

logger = logging.getLogger('services')


@transaction.atomic
def create_device_request_atomic(device_id: int, data: dict) -> tuple:
    """
    Create device request with atomic locking to prevent double-booking
    
    AUDIT FIXES:
    - Uses SELECT FOR UPDATE to lock device row
    - Validates stock within same transaction
    - Prevents race conditions even under high concurrency
    
    Args:
        device_id: Device ID to book
        data: Request data (name, contact, quantity, return_date, purpose)
    
    Returns:
        (success: bool, response_dict: dict, status_code: int)
    """
    try:
        # CRITICAL: Lock the device row for duration of transaction
        # This prevents concurrent requests from double-booking
        device = Device.objects.select_for_update().get(id=device_id)
        
        requested_quantity = int(data['quantity'])
        
        if requested_quantity <= 0:
            return False, {
                'success': False,
                'message': 'Quantity must be greater than 0',
                'error': 'validation_error',
            }, 400
        
        # Refresh inventory (but within locked state)
        device.refresh_inventory()
        
        # Calculate pending and approved quantities
        pending_quantity = 0
        approved_quantity = 0
        
        # Get all requests for this device (still within locked state)
        all_device_requests = DeviceRequest.objects.filter(device=device).select_related('device')
        
        for req in all_device_requests:
            admin_actions = AdminAction.objects.filter(device_request=req).order_by('-created_at')
            latest_action = admin_actions.first()
            
            if not admin_actions.exists():
                pending_quantity += req.requested_quantity
            elif latest_action and latest_action.action_type == 'approve' and latest_action.status != 'returned':
                approved_quantity += latest_action.approved_quantity
        
        # Check if there's enough stock
        total_projected_usage = approved_quantity + pending_quantity + requested_quantity
        
        if total_projected_usage > device.total_quantity:
            available_for_request = device.total_quantity - (approved_quantity + pending_quantity)
            return False, {
                'success': False,
                'message': f'Insufficient stock. Only {available_for_request} items available for new requests',
                'error': 'validation_error',
                'details': {
                    'quantity': [f'Requested quantity would cause overbooking. {available_for_request} items available.']
                }
            }, 400
        
        if requested_quantity > device.current_available:
            return False, {
                'success': False,
                'message': f'Only {device.current_available} items available',
                'error': 'validation_error',
            }, 400
        
        # Parse return date
        expected_return_date = None
        if 'return_date' in data and data['return_date']:
            try:
                expected_return_date = datetime.strptime(data['return_date'], '%Y-%m-%d').date()
            except ValueError:
                return False, {
                    'success': False,
                    'message': 'Invalid date format. Use YYYY-MM-DD format',
                    'error': 'validation_error',
                }, 400
        
        # Create device request (all validations passed)
        device_request = DeviceRequest.objects.create(
            device=device,
            name=data['name'].strip(),
            roll_no=data.get('roll_no', 'N/A'),
            contact=data['contact'].strip(),
            requested_quantity=requested_quantity,
            expected_return_date=expected_return_date,
            purpose=data.get('purpose', ''),
            user_unique_id=data.get('user_unique_id')  # Add user_unique_id for JWT cart
        )
        
        # Log successful booking
        logger.info(
            f"Device request created atomically",
            extra={
                'device_id': device_id,
                'request_id': device_request.id,
                'quantity': requested_quantity,
                'available_after': device.current_available
            }
        )
        
        # Success response
        return True, {
            'success': True,
            'message': 'Device request submitted successfully',
            'request_id': f'REQ{device_request.id:03d}',
            'data': {
                'id': device_request.id,
                'device_id': device_request.device.id,
                'name': device_request.name,
                'contact': device_request.contact,
                'roll_no': device_request.roll_no,
                'quantity': device_request.requested_quantity,
                'return_date': device_request.expected_return_date.strftime('%Y-%m-%d') if device_request.expected_return_date else None,
                'purpose': device_request.purpose,
                'status': 'pending',
                'created_at': device_request.created_at.isoformat()
            }
        }, 200
        
    except Device.DoesNotExist:
        return False, {
            'success': False,
            'message': 'Device not found',
            'error': 'not_found'
        }, 404
    
    except Exception as e:
        logger.error(f"Atomic booking failed: {str(e)}", exc_info=True)
        return False, {
            'success': False,
            'message': 'Failed to submit request',
            'error': 'server_error'
        }, 500


def replace_device_request_view(old_view_code: str) -> str:
    """
    Helper to replace old view code with atomic version
    
    In services/api_views.py, replace the post() method of DeviceRequestAPIView with:
    
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
                    }, status=400)
            
            # Use atomic function
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
    """
    pass
