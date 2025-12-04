# Generated manually for audit fixes

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0002_alter_member_user_id'),
    ]

    operations = [
        # Change device_id from UUIDField to CharField
        migrations.AlterField(
            model_name='device',
            name='device_id',
            field=models.CharField(
                db_index=True,
                help_text='Immutable device identifier from mobile app (UUID or device fingerprint)',
                max_length=255
            ),
        ),
        # Add device_model field
        migrations.AddField(
            model_name='device',
            name='device_model',
            field=models.CharField(
                blank=True,
                default='',
                help_text="Device model (e.g., 'SM-G998B', 'iPhone14,2')",
                max_length=100
            ),
        ),
        # Add os_version field
        migrations.AddField(
            model_name='device',
            name='os_version',
            field=models.CharField(
                blank=True,
                default='',
                help_text="Operating system version (e.g., 'Android 13', 'iOS 16.5')",
                max_length=50
            ),
        ),
        # Change device_name to non-null with default
        migrations.AlterField(
            model_name='device',
            name='device_name',
            field=models.CharField(
                blank=True,
                default='',
                help_text="Human-readable device name (e.g., 'iPhone 14 Pro')",
                max_length=200
            ),
        ),
        # Change last_refresh_token_jti to non-null with default
        migrations.AlterField(
            model_name='device',
            name='last_refresh_token_jti',
            field=models.CharField(
                blank=True,
                default='',
                help_text='JTI of last issued refresh token (prevents token replay)',
                max_length=255
            ),
        ),
        # Add created_at index
        migrations.AddIndex(
            model_name='device',
            index=models.Index(fields=['created_at'], name='authenticat_created_idx'),
        ),
    ]
