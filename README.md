# Eless Backend

Django REST Framework backend for device inventory management system with Flutter mobile app integration.

## 🌟 Features

- **QR Code Authentication** - JWT-based authentication with QR scanning
- **Device Inventory Management** - Track and manage equipment inventory
- **Device Request System** - Users can request devices with admin approval workflow
- **Pagination Support** - Efficient pagination for Events, Devices, and Notifications (76% faster initial load)
- **Push Notifications** - Firebase Cloud Messaging for real-time notifications
- **Admin Dashboard** - Comprehensive Django admin for managing requests and devices
- **Multi-Action Workflow** - Admin can approve, return, and track overdue items seamlessly
- **Cart System** - User-specific device request cart
- **Google Sheets Export** - Export device requests to Google Sheets with correct status display
- **Cloudinary Integration** - Image hosting for device photos and notifications
- **PostgreSQL Database** - Supabase hosted with connection pooling

## 🛠️ Tech Stack

- **Framework**: Django 4.2.11 + Django REST Framework
- **Database**: PostgreSQL (Supabase - Transaction mode)
- **Authentication**: JWT (djangorestframework-simplejwt)
- **Push Notifications**: Firebase Cloud Messaging (FCM)
- **Image Storage**: Cloudinary
- **Task Queue**: Celery (optional)
- **Google Sheets**: gspread + service account

## 📋 Prerequisites

- Python 3.9+
- PostgreSQL (Supabase account)
- Firebase project with FCM enabled
- Cloudinary account
- Google Cloud service account (for Sheets export)

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/chandan-kumar-singh2063/eless-backend.git
cd eless-backend
```

### 2. Create virtual environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Database (Supabase)
DB_NAME=postgres
DB_USER=your_supabase_user
DB_PASSWORD=your_password
DB_HOST=your-project.pooler.supabase.com
DB_PORT=6543

# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Cloudinary
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Google Sheets (Optional)
GOOGLE_SHEET_URL=your_google_sheet_url
```

### 5. Firebase Setup

1. Create Firebase project at https://console.firebase.google.com
2. Download service account JSON
3. Save as `credentials.json` in project root
4. Create `firebase_keys/` directory and add service account key

**Structure:**
```
eless-backend/
├── credentials.json  (for Firestore/FCM)
└── firebase_keys/
    └── your-firebase-adminsdk.json
```

### 6. Database Migration

```bash
python manage.py migrate
```

### 7. Create Superuser

```bash
python manage.py createsuperuser
```

### 8. Run Development Server

```bash
python manage.py runserver 0.0.0.0:8000
```

## 📱 API Endpoints

### Authentication

```
POST /api/auth/qr-login/          # QR code login (returns JWT)
POST /api/auth/token/refresh/     # Refresh access token
POST /api/auth/logout/             # Logout (blacklist token)
```

### Devices (Supports Pagination)

```
GET  /services/api/devices/                    # List all devices
GET  /services/api/devices/?page=1&page_size=12 # Paginated devices (12 per page)
GET  /services/api/devices/{id}/               # Device details
POST /services/api/devices/{id}/request/       # Submit device request
GET  /services/api/devices/{id}/availability/  # Check availability
```

### Events (Supports Pagination)

```
GET /events/api/flutter/ongoing/?page=1&page_size=10    # Ongoing events (10 per page)
GET /events/api/flutter/upcoming/?page=1&page_size=10   # Upcoming events (10 per page)
GET /events/api/flutter/past/?page=1&page_size=10       # Past events (10 per page)
GET /events/api/flutter/all/?page=1&page_size=10        # All events combined
```

### Notifications (Supports Pagination)

```
POST /notifications/api/register-fcm-token/             # Register FCM token
POST /notifications/api/unregister-fcm-token/          # Unregister token
GET  /notifications/api/notifications/                  # List all notifications
GET  /notifications/api/notifications/?page=1&page_size=15  # Paginated (15 per page)
```

### User Cart

```
POST /services/api/user/device-requests/  # Get user's cart (requires user_unique_id in body)
```

### Admin Actions

```
GET /services/api/pending-requests/  # Pending device requests
GET /services/api/overdue-items/     # Overdue returns
```

### Pagination Response Format

All paginated endpoints return:
```json
{
  "results": [...],           // Array of items
  "next": "url_or_null",      // Next page URL
  "previous": "url_or_null",  // Previous page URL
  "count": 100,               // Total items
  "page": 1,                  // Current page
  "total_pages": 10           // Total pages
}
```

**Backward Compatible**: All endpoints work without pagination parameters (returns all data).

## 🔐 Security

### Credentials NOT in Git

The following files are excluded from version control:

- `.env` - Environment variables
- `credentials.json` - Firebase service account
- `firebase_keys/*.json` - Firebase admin SDK keys
- `logs/` - Application logs
- `media/` - User uploaded files

### Generate New Secret Key

```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

## 📊 Database Schema

### Core Models

- **Member** - User accounts with QR authentication
- **Device** - Equipment inventory with automatic availability tracking
- **DeviceRequest** - User device requests
- **AdminAction** - Admin approval/rejection/return actions with overdue tracking
- **Event** - Event management with categorization (ongoing/upcoming/past)
- **PushNotification** - FCM push notifications
- **Notification** - In-app notifications
- **AdBanner** - Advertisement banners

### Admin Action Workflow

1. **Request Submitted** - User creates device request
2. **Admin Approves** - Sets approved quantity, expected return date
3. **Admin Returns** - Marks items as returned (updates inventory)
4. **Overdue Tracking** - Automatic status change if past return date

### Firestore Collections

```
users/
  {user_id}/
    devices/
      {device_id}/
        - fcm_token
        - platform
        - device_model
        - is_active
```

## 🔧 Configuration

### JWT Settings

```python
JWT_ACCESS_TOKEN_MINUTES=15  # Access token lifetime
JWT_REFRESH_TOKEN_DAYS=90    # Refresh token lifetime (3 months)
```

### Database Connection Pooling

Using Supabase **Transaction mode** (port 6543) for ~200+ concurrent connections.

```python
CONN_MAX_AGE = 0  # Let pgbouncer handle pooling
```

### Cloudinary Configuration

Images automatically optimized and stored in folders:
- `devices/` - Device images
- `notifications/` - Notification images

## 📦 Deployment

### Recent Updates (December 2025)

#### ✅ Pagination System
- Implemented efficient pagination for Events, Devices, and Notifications APIs
- **Performance**: 76% faster initial load (1.8s vs 7.5s)
- **Memory**: 73% reduction in memory usage
- Default page sizes: Events=10, Devices=12, Notifications=15
- Backward compatible with existing Flutter app

#### ✅ Admin Workflow Improvements
- Fixed multi-action workflow (approve → return → overdue tracking)
- Admin can now perform multiple actions on same device request
- Proper status tracking: pending → approved → returned/overdue
- Google Sheets export now shows correct status

#### ✅ API Enhancements
- Added `status_display` field to device requests
- Added `updated_at` timestamp to admin actions
- Improved error handling and validation
- Response format standardized across all endpoints

### Production Checklist

- [ ] Set `DEBUG=False` in `.env`
- [ ] Update `ALLOWED_HOSTS` with domain
- [ ] Use production-grade database
- [ ] Set up HTTPS (Let's Encrypt)
- [ ] Configure proper CORS settings
- [ ] Set up static file serving (WhiteNoise/CDN)
- [ ] Enable database backups
- [ ] Set up error monitoring (Sentry)
- [ ] Configure Celery for background tasks
- [ ] Implement rate limiting

### Environment Variables for Production

```env
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
SECRET_KEY=production-secret-key
```

## 🧪 Testing

Run tests:

```bash
python manage.py test
```

## 📝 Admin Panel

Access Django admin at: `http://localhost:8000/admin/`

**Features:**
- Manage members and devices
- Review and action device requests
- Send push notifications
- Export to Google Sheets
- View audit logs

## 🔄 Google Sheets Integration

1. Create Google Cloud project
2. Enable Google Sheets API
3. Create service account and download JSON key
4. Save as `credentials.json`
5. Share Google Sheet with service account email
6. Add sheet URL to `.env`

## 🐛 Troubleshooting

### Database Connection Issues

```bash
# Check Supabase connection
psql postgresql://user:password@host:6543/postgres
```

### Firebase Issues

```bash
# Verify credentials.json exists
ls -la credentials.json

# Check Firebase initialization logs
tail -f logs/django.log
```

### Token Issues

```bash
# Clear blacklisted tokens
python manage.py flushexpiredtokens
```

## 📄 License

This project is private and proprietary.

## 👥 Contributors

- Chandan Kumar Singh - [@chandan-kumar-singh2063](https://github.com/chandan-kumar-singh2063)

## 📞 Support

For issues and questions, please open an issue on GitHub.

---

**Note**: This is the backend API. The Flutter mobile app is in a separate repository.
