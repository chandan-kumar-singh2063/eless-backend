from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
import pytz
import cloudinary.uploader
from cloudinary.models import CloudinaryField

def device_image_upload_path(instance, filename):
    """Dynamic upload path for device images in Cloudinary devices folder"""
    ext = filename.split('.')[-1]
    safe_name = "".join(c for c in instance.name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_name = safe_name.replace(' ', '_').lower()
    new_filename = f"{safe_name}_{instance.id or 'new'}.{ext}"
    return f"devices/{new_filename}"

class Device(models.Model):
    name = models.CharField(max_length=255, help_text="Device name")
    description = models.TextField(help_text="Device description and specifications")
    
    # Cloudinary image field
    image = CloudinaryField(
        'image',
        folder='devices',
        blank=True,
        null=True,
        help_text="Device image will be uploaded to Cloudinary devices folder",
        transformation={
            'width': 800,
            'height': 600,
            'crop': 'fill',
            'quality': 'auto',
            'fetch_format': 'auto'
        }
    )
    
    # Inventory fields
    total_quantity = models.PositiveIntegerField(
        default=1,
        help_text="Total quantity available in inventory"
    )
    current_available = models.PositiveIntegerField(
        default=0,
        help_text="Currently available quantity (auto-calculated)"
    )
    total_booked = models.PositiveIntegerField(
        default=0,
        help_text="Total booked/approved quantity (auto-calculated)"
    )
    is_available = models.BooleanField(
        default=True,
        help_text="Whether device is available for booking"
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def get_cloudinary_url(self):
        """Get optimized Cloudinary URL"""
        if self.image:
            return str(self.image.url)
        return None
    
    def get_cloudinary_thumbnail_url(self):
        """Get thumbnail version"""
        if self.image:
            from cloudinary import CloudinaryImage
            return CloudinaryImage(str(self.image)).build_url(
                width=300, height=200, crop='fill', quality='auto', fetch_format='auto'
            )
        return None

    def calculate_inventory(self):
        """Calculate current inventory based on approved/returned admin actions"""
        # Get all approved admin actions (these reduce inventory)
        approved_actions = self.adminaction_set.filter(action_type='approve')
        total_approved = sum(action.approved_quantity for action in approved_actions)
        
        # Get all returned admin actions (these restore inventory)
        returned_actions = self.adminaction_set.filter(action_type='return')
        total_returned = sum(action.approved_quantity for action in returned_actions)
        
        # Calculate current booked quantity (approved - returned)
        self.total_booked = max(0, total_approved - total_returned)
        
        # Calculate available quantity
        self.current_available = max(0, self.total_quantity - self.total_booked)
        self.is_available = self.current_available > 0

    def save(self, *args, **kwargs):
        """Auto-calculate inventory on save"""
        if self.pk:
            self.calculate_inventory()
        else:
            self.current_available = self.total_quantity
            self.total_booked = 0
            self.is_available = True
        super().save(*args, **kwargs)
    
    def refresh_inventory(self):
        """Manually refresh inventory"""
        self.calculate_inventory()
        Device.objects.filter(pk=self.pk).update(
            current_available=self.current_available,
            total_booked=self.total_booked,
            is_available=self.is_available,
            updated_at=timezone.now()
        )
    
    def __str__(self):
        return f"{self.name} (Available: {self.current_available}/{self.total_quantity})"

    class Meta:
        ordering = ['name']
        verbose_name = 'Device'
        verbose_name_plural = 'Devices'

# TABLE 1: Device Requests (User submissions only)
class DeviceRequest(models.Model):
    """User device requests - No admin actions here"""
    
    # User identification (for JWT authentication)
    user_unique_id = models.CharField(
        max_length=50,
        db_index=True,
        help_text="User unique ID (e.g., ROBO-2024-001)",
        blank=True,
        null=True
    )
    
    # Device and user info
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    name = models.CharField(max_length=255, help_text="Student/User name")
    roll_no = models.CharField(max_length=50, help_text="Roll number", default='N/A')
    contact = models.CharField(max_length=20, help_text="Phone number")
    
    # Request details (what user wants)
    requested_quantity = models.PositiveIntegerField(
        default=1,
        help_text="Quantity requested by user"
    )
    expected_return_date = models.DateField(
        blank=True, null=True,
        help_text="When user plans to return the device"
    )
    purpose = models.TextField(
        blank=True,
        help_text="Why user needs this device"
    )
    
    # Request timestamps
    request_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def get_nepal_now(self):
        """Get Nepal timezone date"""
        nepal_tz = pytz.timezone('Asia/Kathmandu')
        return timezone.now().astimezone(nepal_tz).date()
    
    def __str__(self):
        return f"{self.name} - {self.device.name} (Requested: {self.requested_quantity})"

    class Meta:
        ordering = ['-request_date', '-created_at']
        verbose_name = 'Device Request'
        verbose_name_plural = 'Device Requests'

# TABLE 2: Admin Actions (Admin decisions and tracking)
class AdminAction(models.Model):
    """Admin actions on device requests - Simplified workflow"""
    
    ACTION_TYPES = [
        ('approve', 'Approved'),
        ('reject', 'Rejected'),
        ('return', 'Returned'),
    ]
    
    STATUS_CHOICES = [
        ('on_service', 'On Service'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
    ]
    
    # Core fields only
    device_request = models.ForeignKey(DeviceRequest, on_delete=models.CASCADE)
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    approved_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Quantity approved by admin"
    )
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='on_service',
        help_text="Current status: on_service, returned, or overdue"
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        """Auto-update status based on return date and refresh inventory"""
        # For approved requests, auto-set status based on DeviceRequest return date
        # (This is just for record-keeping, doesn't affect inventory)
        if self.action_type == 'approve' and self.device_request.expected_return_date:
            nepal_tz = pytz.timezone('Asia/Kathmandu')
            today = timezone.now().astimezone(nepal_tz).date()
            
            # Auto-set status for record-keeping only
            if self.status != 'returned':
                if today > self.device_request.expected_return_date:
                    self.status = 'overdue'
                else:
                    self.status = 'on_service'
        
        # Save action first
        super().save(*args, **kwargs)
        
        # Update device inventory based on action_type (approve/return/reject)
        self.device.refresh_inventory()

    def is_overdue(self):
        """Check if this approval is overdue based on DeviceRequest return date"""
        if (self.action_type == 'approve' and 
            self.status != 'returned' and 
            self.device_request.expected_return_date):
            nepal_tz = pytz.timezone('Asia/Kathmandu')
            today = timezone.now().astimezone(nepal_tz).date()
            return today > self.device_request.expected_return_date
        return False

    def get_user_name(self):
        """Get the name of user who made the request"""
        return self.device_request.name

    def get_user_contact(self):
        """Get contact of user who made the request"""
        return self.device_request.contact
    
    def __str__(self):
        if self.action_type == 'approve':
            return f"{self.device.name} - Approved ({self.approved_quantity}) - {self.get_status_display()}"
        else:
            return f"{self.device.name} - {self.get_action_type_display()}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Admin Action'
        verbose_name_plural = 'Admin Actions'
