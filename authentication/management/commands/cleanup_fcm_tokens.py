"""
Management command to cleanup invalid FCM tokens from Firestore

AUDIT FIXES:
✅ Scans all tokens for validity
✅ Removes only invalid/unregistered tokens
✅ Batch operations for scalability
✅ Detailed logging and metrics

Usage:
    python manage.py cleanup_fcm_tokens

Schedule with cron (daily at 2 AM):
    0 2 * * * cd /path/to/project && /path/to/venv/bin/python manage.py cleanup_fcm_tokens >> /var/log/fcm_cleanup.log 2>&1
"""

from django.core.management.base import BaseCommand
from authentication.firebase_client_v2 import cleanup_all_invalid_tokens, get_push_metrics
import logging

logger = logging.getLogger('authentication.firebase')


class Command(BaseCommand):
    help = 'Cleanup invalid FCM tokens from Firestore'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        """Execute the cleanup task"""
        dry_run = options.get('dry_run', False)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        
        self.stdout.write(self.style.WARNING('Starting FCM token cleanup...'))
        
        try:
            # Run cleanup
            cleaned_count = cleanup_all_invalid_tokens() if not dry_run else 0
            
            # Get metrics
            metrics = get_push_metrics()
            
            self.stdout.write(self.style.SUCCESS(f'\n✓ FCM token cleanup completed'))
            self.stdout.write(f'  - Invalid tokens removed: {cleaned_count}')
            self.stdout.write(f'  - Total tokens cleaned (lifetime): {metrics["tokens_cleaned"]}')
            self.stdout.write(f'  - Push notifications sent (lifetime): {metrics["total_sent"]}')
            self.stdout.write(f'  - Success rate: {metrics["total_success"]}/{metrics["total_sent"]}')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ FCM token cleanup failed: {str(e)}'))
            logger.error(f"Cleanup command failed: {str(e)}", exc_info=True)
            raise
