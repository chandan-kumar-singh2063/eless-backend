"""
Helper script to verify all required credential files are present.
Run this after cloning the repository.
"""

import os
import sys
from pathlib import Path

REQUIRED_FILES = {
    '.env': 'Environment variables (copy from .env.example)',
    'credentials.json': 'Google Sheets API credentials',
    'firebase_keys/': 'Firebase Admin SDK keys (at least 1 JSON file)',
}

def check_file(filepath, description):
    """Check if file exists and is not empty."""
    path = Path(filepath)
    
    if filepath.endswith('/'):  # Directory
        if not path.exists():
            print(f"❌ Missing: {filepath} - {description}")
            return False
        json_files = list(path.glob('*.json'))
        if not json_files:
            print(f"⚠️  Empty: {filepath} - {description}")
            return False
        print(f"✅ Found: {filepath} ({len(json_files)} JSON files)")
        for json_file in json_files:
            print(f"   - {json_file.name}")
        return True
    else:  # File
        if not path.exists():
            print(f"❌ Missing: {filepath} - {description}")
            return False
        if path.stat().st_size == 0:
            print(f"⚠️  Empty: {filepath} - {description}")
            return False
        print(f"✅ Found: {filepath} ({path.stat().st_size} bytes)")
        return True

def main():
    print("🔐 Eless Backend - Credential Setup Checker")
    print("="*60 + "\n")
    
    all_present = True
    for filepath, description in REQUIRED_FILES.items():
        if not check_file(filepath, description):
            all_present = False
        print()
    
    print("="*60)
    
    if all_present:
        print("✅ All required credential files are present!")
        print("\n📋 Next steps:")
        print("  1. python manage.py migrate")
        print("  2. python manage.py createsuperuser")
        print("  3. python manage.py runserver 0.0.0.0:8000")
    else:
        print("❌ Some credential files are missing!")
        print("\n📋 Setup instructions:")
        print("  1. Copy .env.example to .env and fill in values")
        print("  2. Add credentials.json from Google Cloud Console")
        print("  3. Add Firebase Admin SDK JSON to firebase_keys/")
        print("\n📖 See SECURITY_SETUP.md for detailed instructions")
        sys.exit(1)

if __name__ == '__main__':
    main()
