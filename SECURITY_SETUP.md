# 🔐 Security Setup Guide

This document explains how to secure your deployment and set up credentials.

## ⚠️ NEVER Commit These Files

The following files contain sensitive data and are already in `.gitignore`:

```
.env                           # Database passwords, API keys
credentials.json              # Google service account private key
firebase_keys/*.json          # Firebase admin SDK keys
logs/                         # May contain sensitive data
media/                        # User uploads
```

## 📝 Setup Checklist

### 1. Environment Variables (.env)

Copy the example and fill in your credentials:

```bash
cp .env.example .env
```

**Required variables:**
- `SECRET_KEY` - Django secret key (generate new one!)
- `DB_PASSWORD` - Your Supabase database password
- `CLOUDINARY_API_SECRET` - Your Cloudinary API secret
- `DB_USER` - Your Supabase username
- `CLOUDINARY_CLOUD_NAME` - Your Cloudinary cloud name
- `CLOUDINARY_API_KEY` - Your Cloudinary API key

### 2. Generate Django Secret Key

```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

Copy the output to `.env`:

```env
SECRET_KEY=your-generated-secret-key-here
```

### 3. Firebase Credentials

#### A. Google Sheets Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project or select existing
3. Enable **Google Sheets API**
4. Create **Service Account**
5. Download JSON key
6. Save as `credentials.json` in project root

#### B. Firebase Admin SDK

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Go to **Project Settings** → **Service Accounts**
4. Click **Generate New Private Key**
5. Save JSON file to `firebase_keys/` directory

**File structure:**
```
robotics_club/
├── credentials.json  # Google Sheets service account
└── firebase_keys/
    └── your-project-firebase-adminsdk.json
```

### 4. Supabase Database

1. Go to [Supabase Dashboard](https://supabase.com/dashboard)
2. Create new project or select existing
3. Go to **Settings** → **Database**
4. Use **Transaction mode** pooler (port 6543)

Copy connection details to `.env`:

```env
DB_NAME=postgres
DB_USER=postgres.xxxxxxxxxxxx
DB_PASSWORD=your_password
DB_HOST=aws-x-xx-xxxx-x.pooler.supabase.com
DB_PORT=6543
```

### 5. Cloudinary Setup

1. Go to [Cloudinary Console](https://cloudinary.com/console)
2. Copy **Cloud name**, **API Key**, **API Secret**

Add to `.env`:

```env
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=123456789012345
CLOUDINARY_API_SECRET=your_api_secret
```

### 6. Google Sheets Integration (Optional)

1. Create Google Sheet
2. Share with service account email from `credentials.json`:
   ```
   your-service-account@project.iam.gserviceaccount.com
   ```
3. Give **Editor** access
4. Copy sheet URL to `.env`:

```env
GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
```

## 🔒 Production Security

### Change These Before Deployment:

1. **Django Secret Key** - Generate new production key
2. **DEBUG** - Set to `False`
3. **ALLOWED_HOSTS** - Add your domain
4. **Database Password** - Use strong password
5. **HTTPS** - Enable SSL certificate

### Production `.env`:

```env
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com
SECRET_KEY=production-secret-key-at-least-50-characters-long
```

## 🧹 Clean Up Before Push

Before pushing to GitHub, verify:

```bash
# Check what will be committed
git status

# Verify .env is ignored
git check-ignore .env

# Verify credentials are ignored
git check-ignore credentials.json
git check-ignore firebase_keys/*.json

# All should return the filename if properly ignored
```

## 🚨 If You Accidentally Committed Secrets

If you already pushed sensitive data:

1. **Immediately rotate all credentials:**
   - Generate new Django SECRET_KEY
   - Reset Supabase password
   - Regenerate Cloudinary API secret
   - Create new Firebase service accounts

2. **Remove from Git history:**

```bash
# Remove sensitive file from all commits
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# Force push (WARNING: Rewrites history)
git push origin --force --all
```

3. **Alternative: Use BFG Repo-Cleaner:**

```bash
# Install BFG
brew install bfg  # macOS
# or download from: https://rtyley.github.io/bfg-repo-cleaner/

# Remove .env from history
bfg --delete-files .env

# Clean up
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Force push
git push --force
```

## ✅ Verification

After setup, verify everything works:

```bash
# Test database connection
python manage.py check

# Run migrations
python manage.py migrate

# Test server startup
python manage.py runserver
```

## 📞 Need Help?

If you encounter issues:
1. Check `.env` file matches `.env.example` structure
2. Verify all credentials are correct
3. Check file permissions on `credentials.json`
4. Review Django logs in `logs/` directory

---

**Remember:** Never share your `.env` or `credentials.json` files!
