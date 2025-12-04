# Local development settings - Use when Supabase is not accessible
# Usage: python manage.py migrate --settings=robotics_club.local_dev_settings

from .settings import *
import os

# Allow all hosts in local development
ALLOWED_HOSTS = ['*']

# Override database to use SQLite for local development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'local_dev.sqlite3'),
    }
}

# Disable Cloudinary for local development
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

print("🔧 Using LOCAL SQLite database for development")
