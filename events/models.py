from django.db import models
from django.utils import timezone
import pytz
import os

def event_image_upload_path(instance, filename):
    """
    Dynamic upload path based on event type using Nepal timezone
    """
    # Get Nepal timezone
    nepal_tz = pytz.timezone('Asia/Kathmandu')
    today = timezone.now().astimezone(nepal_tz).date()
    
    if instance.date > today:
        folder = 'upcoming'
    elif instance.date == today:
        folder = 'ongoing'
    else:
        folder = 'past'
    
    ext = filename.split('.')[-1]
    safe_title = "".join(c for c in instance.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_title = safe_title.replace(' ', '_').lower()
    new_filename = f"{safe_title}_{instance.id or 'new'}.{ext}"
    
    return f"events/{folder}/{new_filename}"

class Event(models.Model):
    EVENT_TYPES = [
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'), 
        ('past', 'Past'),
    ]
    
    REGISTRATION_STATUS = [
        ('not_started', 'Registration Not Started'),
        ('open', 'Registration Open'),
        ('closed', 'Registration Closed'),
        ('full', 'Registration Full'),
        ('no_registration', 'No Registration Required'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField()
    venue = models.CharField(
        max_length=300, 
        help_text="Event venue/location",
        default="TBD"
    )
    image = models.ImageField(
        upload_to=event_image_upload_path,
        blank=True, 
        null=True,
        help_text="Event image will be automatically organized in Cloudinary by event type"
    )
    date = models.DateField(help_text="Event date - determines if event is upcoming/ongoing/past")
    time = models.TimeField(
        blank=True,
        null=True,
        help_text="Event time (optional)"
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default='upcoming')
    
    # Registration fields
    registration_url = models.URLField(
        max_length=500,
        blank=True,
        null=True,
        help_text="Google Form URL for event registration",
        verbose_name="Registration URL"
    )
    registration_start_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date when registration opens (leave blank if no registration required)",
        verbose_name="Registration Opens On"
    )
    registration_end_date = models.DateField(
        blank=True,
        null=True,
        help_text="Date when registration closes (leave blank if no registration required)",
        verbose_name="Registration Closes On"
    )
    registration_status = models.CharField(
        max_length=20, 
        choices=REGISTRATION_STATUS, 
        default='no_registration',
        help_text="Auto-calculated based on registration dates"
    )
    
    # Timestamps for admin tracking
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Badge system for Flutter app
    is_new = models.BooleanField(
        default=True,
        help_text="Show 'NEW' badge in Flutter app (red dot). Automatically set to True for new events."
    )
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'Club Event'
        verbose_name_plural = 'Club Events'
    
    def get_nepal_today(self):
        """Get current date in Nepal timezone"""
        nepal_tz = pytz.timezone('Asia/Kathmandu')
        return timezone.now().astimezone(nepal_tz).date()
    
    def get_nepal_now(self):
        """Get current datetime in Nepal timezone"""
        nepal_tz = pytz.timezone('Asia/Kathmandu')
        return timezone.now().astimezone(nepal_tz)
    
    def save(self, *args, **kwargs):
        """Automatically set event_type and registration_status using Nepal time"""
        today = self.get_nepal_today()  # Use Nepal date
        
        # CRITICAL FIX (Bug #6): Don't move images when event_type changes
        # This prevents Cloudinary URL changes that break Flutter cache
        # Images stay in their original upload folders permanently
        
        # Set event type based on Nepal date
        if self.date > today:
            self.event_type = 'upcoming'
        elif self.date == today:
            self.event_type = 'ongoing'
        else:
            self.event_type = 'past'
        
        # Set registration status using Nepal time
        self.registration_status = self.calculate_registration_status()
        
        super().save(*args, **kwargs)
    
    def calculate_registration_status(self):
        """Calculate registration status using Nepal time"""
        today = self.get_nepal_today()  # Use Nepal date
        
        if not self.registration_url:
            return 'no_registration'
        
        if not self.registration_start_date or not self.registration_end_date:
            if self.event_type == 'upcoming':
                return 'open'
            else:
                return 'no_registration'
        
        # Check based on Nepal dates
        if today < self.registration_start_date:
            return 'not_started'
        elif today > self.registration_end_date:
            return 'closed'
        elif self.registration_start_date <= today <= self.registration_end_date:
            return 'open'
        
        return 'no_registration'
    
    def is_registration_open(self):
        """Check if registration is currently open"""
        return self.registration_status == 'open'
    
    def registration_status_display(self):
        """Get human-readable registration status"""
        status_display = {
            'not_started': '⏳ Opens Soon',
            'open': '✅ Open Now',
            'closed': '❌ Closed',
            'full': '🔒 Full',
            'no_registration': '➖ No Registration'
        }
        return status_display.get(self.registration_status, '❓ Unknown')
    
    def days_until_registration_opens(self):
        """Calculate days until registration opens using Nepal time"""
        if not self.registration_start_date:
            return None
        
        today = self.get_nepal_today()
        delta = self.registration_start_date - today
        
        if delta.days > 0:
            return f"Opens in {delta.days} days"
        elif delta.days == 0:
            return "Opens today"
        else:
            return "Already opened"
    
    def days_until_registration_closes(self):
        """Calculate days until registration closes using Nepal time"""
        if not self.registration_end_date:
            return None
        
        today = self.get_nepal_today()
        delta = self.registration_end_date - today
        
        if delta.days > 0:
            return f"Closes in {delta.days} days"
        elif delta.days == 0:
            return "Closes today"
        else:
            return "Already closed"
    
    def days_until_event(self):
        """Calculate days until/since event using Nepal time"""
        today = self.get_nepal_today()  # Use Nepal date
        delta = self.date - today
        
        if delta.days > 0:
            return f"In {delta.days} days"
        elif delta.days == 0:
            return "TODAY"
        else:
            return f"{abs(delta.days)} days ago"
    
    def is_today(self):
        """Check if event is today using Nepal time"""
        return self.date == self.get_nepal_today()  # Use Nepal date
    
    def get_formatted_time(self):
        """Get formatted time for Flutter app"""
        if self.time:
            return self.time.strftime('%I:%M %p')  # Format: "10:00 AM"
        return None
    
    def get_cloudinary_folder(self):
        """Get the Cloudinary folder for this event"""
        return f"events/{self.event_type}"
    
    def _move_image_to_correct_folder(self, old_event_type):
        """Move image to correct Cloudinary folder when event type changes"""
        if not self.image:
            return
            
        try:
            import cloudinary
            import cloudinary.uploader
            
            # Get current image public_id
            current_public_id = self.image.name.replace(f'events/{old_event_type}/', '').split('.')[0]
            old_public_id = f"events/{old_event_type}/{current_public_id}"
            
            # Create new path
            safe_title = "".join(c for c in self.title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            safe_title = safe_title.replace(' ', '_').lower()
            new_public_id = f"events/{self.event_type}/{safe_title}_{self.id}"
            
            # Move/rename the image in Cloudinary
            result = cloudinary.uploader.rename(old_public_id, new_public_id)
            
            # Update the image field with new path
            ext = self.image.name.split('.')[-1]
            self.image.name = f"events/{self.event_type}/{safe_title}_{self.id}.{ext}"
            
            # Save without triggering the save method again
            Event.objects.filter(pk=self.pk).update(image=self.image.name)
            
        except Exception as e:
            # Log the error but don't fail the save
            print(f"Error moving image: {e}")
    
    def __str__(self):
        return f"{self.title} - {self.venue} ({self.get_event_type_display()})"
