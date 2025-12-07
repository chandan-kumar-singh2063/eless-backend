from rest_framework import serializers
from .models import DeviceRequest, AdminAction, Device

class UserDeviceRequestSerializer(serializers.ModelSerializer):
    """Serializer for user-specific device requests (Cart feature)"""
    
    device_id = serializers.IntegerField(source='device.id', read_only=True)
    device_name = serializers.CharField(source='device.name', read_only=True)
    device_image = serializers.SerializerMethodField()
    admin_action = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    approved_quantity = serializers.SerializerMethodField()
    rejection_reason = serializers.SerializerMethodField()
    return_date = serializers.DateField(source='expected_return_date', read_only=True)
    
    class Meta:
        model = DeviceRequest
        fields = [
            'id',
            'device_id',
            'device_name',
            'device_image',
            'requested_quantity',
            'approved_quantity',
            'admin_action',
            'status',
            'return_date',
            'request_date',
            'rejection_reason',
        ]
    
    def get_device_image(self, obj):
        """Return device image URL"""
        if obj.device.image:
            return obj.device.get_cloudinary_url()
        return None
    
    def get_admin_action(self, obj):
        """Get latest admin action type"""
        latest_action = AdminAction.objects.filter(
            device_request=obj
        ).order_by('-created_at').first()
        
        if not latest_action:
            return 'pending'
        
        # Handle return action
        if latest_action.action_type == 'return':
            return 'returned'
        elif latest_action.action_type == 'approve':
            # Check if actually returned via status
            if latest_action.status == 'returned':
                return 'returned'
            return 'approved'
        elif latest_action.action_type == 'reject':
            return 'rejected'
        return 'pending'
    
    def get_status(self, obj):
        """Get current status (for approved items only)"""
        latest_action = AdminAction.objects.filter(
            device_request=obj,
            action_type='approve'
        ).order_by('-created_at').first()
        
        if latest_action:
            return latest_action.status
        return None
    
    def get_approved_quantity(self, obj):
        """Get approved quantity (0 if not approved yet)"""
        latest_action = AdminAction.objects.filter(
            device_request=obj,
            action_type='approve'
        ).order_by('-created_at').first()
        
        return latest_action.approved_quantity if latest_action else 0
    
    def get_rejection_reason(self, obj):
        """Get rejection reason if rejected"""
        rejection_action = AdminAction.objects.filter(
            device_request=obj,
            action_type='reject'
        ).order_by('-created_at').first()
        
        # For now, return a generic message since AdminAction doesn't have rejection_reason field
        # You can add this field later if needed
        if rejection_action:
            return "Request was not approved by admin"
        return None
