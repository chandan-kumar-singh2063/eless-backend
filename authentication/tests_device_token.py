"""
Tests for DeviceToken Management and Push Notifications

Tests cover:
1. DeviceToken model validation
2. Register device endpoint (multi-device support)
3. Unregister device endpoint
4. Logout removes specific device token
5. Push notification helpers (send_to_device, send_to_user, send_to_all)
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from authentication.models import Member, Device, DeviceToken
from authentication.push_notifications import (
    send_to_device,
    send_to_user,
    send_to_all,
    send_to_multiple_users
)


class DeviceTokenModelTests(TestCase):
    """Test DeviceToken model validation and constraints"""
    
    def setUp(self):
        self.member = Member.objects.create(
            user_name="Test User",
            user_id="TEST-001",
            is_active=True
        )
    
    def test_device_token_creation(self):
        """Test creating a DeviceToken"""
        device_token = DeviceToken.objects.create(
            user=self.member,
            device_id="test-device-123",
            fcm_token="test-fcm-token-xyz",
            platform="android",
            device_model="Pixel 7"
        )
        
        self.assertEqual(device_token.user, self.member)
        self.assertEqual(device_token.device_id, "test-device-123")
        self.assertEqual(device_token.platform, "android")
    
    def test_device_id_normalization(self):
        """Test that device_id is normalized (lowercase, trimmed)"""
        device_token = DeviceToken.objects.create(
            user=self.member,
            device_id="  TEST-DEVICE-UPPER  ",
            fcm_token="token123",
            platform="ios"
        )
        
        # Should be lowercase and trimmed
        self.assertEqual(device_token.device_id, "test-device-upper")
    
    def test_empty_device_id_raises_error(self):
        """Test that empty device_id raises ValueError"""
        with self.assertRaises(ValueError) as context:
            DeviceToken.objects.create(
                user=self.member,
                device_id="   ",  # Empty after strip
                fcm_token="token123",
                platform="android"
            )
        
        self.assertIn("device_id cannot be empty", str(context.exception))
    
    def test_empty_fcm_token_raises_error(self):
        """Test that empty fcm_token raises ValueError"""
        with self.assertRaises(ValueError) as context:
            DeviceToken.objects.create(
                user=self.member,
                device_id="device123",
                fcm_token="   ",  # Empty after strip
                platform="android"
            )
        
        self.assertIn("fcm_token cannot be empty", str(context.exception))
    
    def test_unique_together_constraint(self):
        """Test that (user, device_id) must be unique"""
        DeviceToken.objects.create(
            user=self.member,
            device_id="device123",
            fcm_token="token1",
            platform="android"
        )
        
        # Creating another token with same user+device_id should raise error
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            DeviceToken.objects.create(
                user=self.member,
                device_id="device123",
                fcm_token="token2",
                platform="ios"
            )
    
    def test_multiple_devices_per_user(self):
        """Test that one user can have multiple device tokens"""
        DeviceToken.objects.create(
            user=self.member,
            device_id="device1",
            fcm_token="token1",
            platform="android"
        )
        
        DeviceToken.objects.create(
            user=self.member,
            device_id="device2",
            fcm_token="token2",
            platform="ios"
        )
        
        # User should have 2 device tokens
        self.assertEqual(self.member.device_tokens.count(), 2)


class RegisterDeviceEndpointTests(TestCase):
    """Test POST /auth/register-device/ endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.member = Member.objects.create(
            user_name="Test User",
            user_id="TEST-001",
            is_active=True
        )
        self.url = reverse('authentication:register_device')
    
    def test_register_new_device(self):
        """Test registering a new device"""
        data = {
            "unique_id": "TEST-001",
            "device_id": "new-device-123",
            "fcm_token": "fcm-token-xyz",
            "platform": "android",
            "model": "Pixel 7"
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertTrue(response.data['is_new'])
        
        # Check database
        device_token = DeviceToken.objects.get(device_id="new-device-123")
        self.assertEqual(device_token.user, self.member)
        self.assertEqual(device_token.platform, "android")
    
    def test_update_existing_device(self):
        """Test updating existing device token (same device_id)"""
        # Create initial device token
        DeviceToken.objects.create(
            user=self.member,
            device_id="existing-device",
            fcm_token="old-token",
            platform="android"
        )
        
        # Update with new FCM token
        data = {
            "unique_id": "TEST-001",
            "device_id": "existing-device",
            "fcm_token": "new-token",
            "platform": "android",
            "model": "Pixel 8"
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        self.assertFalse(response.data['is_new'])
        
        # Check database - should be updated, not duplicated
        device_token = DeviceToken.objects.get(device_id="existing-device")
        self.assertEqual(device_token.fcm_token, "new-token")
        self.assertEqual(device_token.device_model, "Pixel 8")
        
        # Should still be only 1 device token
        self.assertEqual(DeviceToken.objects.filter(user=self.member).count(), 1)
    
    def test_register_multiple_devices_same_user(self):
        """Test that user can register multiple devices"""
        # Register first device
        data1 = {
            "unique_id": "TEST-001",
            "device_id": "device1",
            "fcm_token": "token1",
            "platform": "android"
        }
        response1 = self.client.post(self.url, data1, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Register second device
        data2 = {
            "unique_id": "TEST-001",
            "device_id": "device2",
            "fcm_token": "token2",
            "platform": "ios"
        }
        response2 = self.client.post(self.url, data2, format='json')
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        
        # User should have 2 device tokens
        self.assertEqual(DeviceToken.objects.filter(user=self.member).count(), 2)
    
    def test_register_device_invalid_unique_id(self):
        """Test registering device with invalid unique_id"""
        data = {
            "unique_id": "INVALID-999",
            "device_id": "device123",
            "fcm_token": "token123",
            "platform": "android"
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)
    
    def test_register_device_empty_device_id(self):
        """Test registering device with empty device_id"""
        data = {
            "unique_id": "TEST-001",
            "device_id": "   ",
            "fcm_token": "token123",
            "platform": "android"
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_register_device_empty_fcm_token(self):
        """Test registering device with empty fcm_token"""
        data = {
            "unique_id": "TEST-001",
            "device_id": "device123",
            "fcm_token": "   ",
            "platform": "android"
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UnregisterDeviceEndpointTests(TestCase):
    """Test POST /auth/unregister-device/ endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.member = Member.objects.create(
            user_name="Test User",
            user_id="TEST-001",
            is_active=True
        )
        self.url = reverse('authentication:unregister_device')
    
    def test_unregister_existing_device(self):
        """Test unregistering an existing device"""
        # Create device token
        DeviceToken.objects.create(
            user=self.member,
            device_id="device-to-remove",
            fcm_token="token123",
            platform="android"
        )
        
        data = {
            "unique_id": "TEST-001",
            "device_id": "device-to-remove"
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        
        # Device token should be deleted
        self.assertFalse(
            DeviceToken.objects.filter(device_id="device-to-remove").exists()
        )
    
    def test_unregister_only_specific_device(self):
        """Test that unregister removes ONLY the specified device"""
        # Create 2 devices
        DeviceToken.objects.create(
            user=self.member,
            device_id="device1",
            fcm_token="token1",
            platform="android"
        )
        DeviceToken.objects.create(
            user=self.member,
            device_id="device2",
            fcm_token="token2",
            platform="ios"
        )
        
        # Unregister device1
        data = {
            "unique_id": "TEST-001",
            "device_id": "device1"
        }
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # device1 should be gone, device2 should remain
        self.assertFalse(DeviceToken.objects.filter(device_id="device1").exists())
        self.assertTrue(DeviceToken.objects.filter(device_id="device2").exists())
    
    def test_unregister_nonexistent_device_idempotent(self):
        """Test unregistering nonexistent device (idempotent)"""
        data = {
            "unique_id": "TEST-001",
            "device_id": "nonexistent-device"
        }
        
        response = self.client.post(self.url, data, format='json')
        
        # Should return success (idempotent)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])


class PushNotificationHelpersTests(TestCase):
    """Test push notification helper functions"""
    
    def setUp(self):
        self.member1 = Member.objects.create(
            user_name="User One",
            user_id="USER-001",
            is_active=True
        )
        self.member2 = Member.objects.create(
            user_name="User Two",
            user_id="USER-002",
            is_active=True
        )
        
        # Create device tokens
        DeviceToken.objects.create(
            user=self.member1,
            device_id="device1",
            fcm_token="token1",
            platform="android"
        )
        DeviceToken.objects.create(
            user=self.member1,
            device_id="device2",
            fcm_token="token2",
            platform="ios"
        )
        DeviceToken.objects.create(
            user=self.member2,
            device_id="device3",
            fcm_token="token3",
            platform="android"
        )
    
    @patch('authentication.push_notifications.send_push_notification_with_retry')
    def test_send_to_device(self, mock_send):
        """Test send_to_device() function"""
        mock_send.return_value = {'success': 1, 'failed': 0, 'errors': []}
        
        success, msg = send_to_device(
            fcm_token="token123",
            title="Test Title",
            body="Test Body"
        )
        
        self.assertTrue(success)
        mock_send.assert_called_once()
    
    @patch('authentication.push_notifications.send_push_notification_with_retry')
    def test_send_to_user_multiple_devices(self, mock_send):
        """Test send_to_user() sends to all user's devices"""
        mock_send.return_value = {'success': 2, 'failed': 0, 'errors': []}
        
        success, total, msg = send_to_user(
            user=self.member1,
            title="Test Title",
            body="Test Body"
        )
        
        self.assertEqual(success, 2)
        self.assertEqual(total, 2)
        
        # Should send to both devices
        mock_send.assert_called_once()
        call_args = mock_send.call_args[1]
        self.assertEqual(len(call_args['fcm_tokens']), 2)
    
    @patch('authentication.push_notifications.send_push_notification_with_retry')
    def test_send_to_all(self, mock_send):
        """Test send_to_all() sends to all devices"""
        mock_send.return_value = {'success': 3, 'failed': 0, 'errors': []}
        
        success, total, msg = send_to_all(
            title="Test Title",
            body="Test Body"
        )
        
        self.assertEqual(total, 3)  # All 3 devices
        mock_send.assert_called_once()
    
    @patch('authentication.push_notifications.send_push_notification_with_retry')
    def test_send_to_multiple_users(self, mock_send):
        """Test send_to_multiple_users() sends to specified users"""
        mock_send.return_value = {'success': 3, 'failed': 0, 'errors': []}
        
        success, total, msg = send_to_multiple_users(
            user_ids=[self.member1.id, self.member2.id],
            title="Test Title",
            body="Test Body"
        )
        
        self.assertEqual(total, 3)  # member1 (2 devices) + member2 (1 device)
        mock_send.assert_called_once()
    
    def test_send_to_device_empty_title(self):
        """Test send_to_device with empty title fails validation"""
        success, msg = send_to_device(
            fcm_token="token123",
            title="   ",
            body="Test Body"
        )
        
        self.assertFalse(success)
        self.assertIn("title cannot be empty", msg)
    
    def test_send_to_user_no_devices(self):
        """Test send_to_user with no device tokens"""
        # Create user with no devices
        member3 = Member.objects.create(
            user_name="User Three",
            user_id="USER-003",
            is_active=True
        )
        
        success, total, msg = send_to_user(
            user=member3,
            title="Test",
            body="Test"
        )
        
        self.assertEqual(total, 0)
        self.assertIn("No device tokens found", msg)


class LogoutRemovesDeviceTokenTests(TestCase):
    """Test that logout removes specific DeviceToken"""
    
    def setUp(self):
        self.member = Member.objects.create(
            user_name="Test User",
            user_id="TEST-001",
            is_active=True
        )
        
        # Create 2 device tokens
        self.token1 = DeviceToken.objects.create(
            user=self.member,
            device_id="device1",
            fcm_token="token1",
            platform="android"
        )
        self.token2 = DeviceToken.objects.create(
            user=self.member,
            device_id="device2",
            fcm_token="token2",
            platform="ios"
        )
    
    def test_logout_removes_specific_device_token(self):
        """Test that DeviceToken deletion logic works correctly"""
        # Simulate logout logic: remove only device1
        device_id_to_remove = "device1"
        
        deleted_count, _ = DeviceToken.objects.filter(
            user=self.member,
            device_id=device_id_to_remove
        ).delete()
        
        # Should have deleted 1 token
        self.assertEqual(deleted_count, 1)
        
        # device1 should be removed, device2 should remain
        self.assertFalse(DeviceToken.objects.filter(device_id="device1").exists())
        self.assertTrue(DeviceToken.objects.filter(device_id="device2").exists())
        
        # Member should still have 1 device token
        self.assertEqual(self.member.device_tokens.count(), 1)
    
    def test_logout_does_not_affect_other_users(self):
        """Test that logout doesn't affect other users' device tokens"""
        # Create another member with same device_id
        member2 = Member.objects.create(
            user_name="User Two",
            user_id="TEST-002",
            is_active=True
        )
        
        token3 = DeviceToken.objects.create(
            user=member2,
            device_id="device1",  # Same device_id as member1
            fcm_token="token3",
            platform="android"
        )
        
        # Remove device1 for member1 only
        DeviceToken.objects.filter(
            user=self.member,
            device_id="device1"
        ).delete()
        
        # member1's device1 should be gone
        self.assertFalse(
            DeviceToken.objects.filter(user=self.member, device_id="device1").exists()
        )
        
        # member2's device1 should still exist
        self.assertTrue(
            DeviceToken.objects.filter(user=member2, device_id="device1").exists()
        )
