from django.db import models
from django.utils import timezone
from cloudinary.models import CloudinaryField

class AdBanner(models.Model):
    """Model for advertisement banners displayed in Flutter app carousel"""
    
    # Cloudinary image field for banners
    image = CloudinaryField(
        'image',
        folder='banners',
        help_text="Banner image will be uploaded to Cloudinary banners folder",
        transformation={
            'width': 800,
            'height': 450,
            'crop': 'fill',
            'quality': 'auto',
            'fetch_format': 'auto'
        }
    )
    
    # Banner control fields
    active = models.BooleanField(
        default=True,
        help_text="Whether this banner is active and should be displayed"
    )
    order = models.PositiveIntegerField(
        default=1,
        help_text="Display order (lower numbers appear first)"
    )
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def get_cloudinary_url(self):
        """Get optimized Cloudinary URL"""
        if self.image:
            return str(self.image.url)
        return None
    
    def get_relative_image_path(self):
        """Get relative path for Flutter baseUrl usage"""
        if self.image:
            image_url = str(self.image.url)
            if image_url.startswith('http'):
                # Extract the path part for relative usage
                from urllib.parse import urlparse
                parsed = urlparse(image_url)
                return parsed.path
            return image_url
        return None

    def __str__(self):
        return f"Banner #{self.id} (Order: {self.order})"

    class Meta:
        ordering = ['order', '-created_at']
        verbose_name = 'Ad Banner'
        verbose_name_plural = 'Ad Banners'
