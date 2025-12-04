"""
Comprehensive Unit Tests for QR-based JWT Authentication System

Tests cover:
- QR login success and failure scenarios
- Token refresh with rotation and blacklisting
- Logout endpoint idempotency
- Protected endpoint access control
- Device tracking
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
import uuid

from .models import Member, Device


class MemberModelTests(TestCase):
    """Test Member model functionality"""
    
    def setUp(self):
        self.member = Member.objects.create(
            user_name="Test User",
            user_id="TEST-001"
        )
    
    def test_member_creation(self):
        """Test member is created correctly"""
        self.assertEqual(self.member.user_name, "Test User")
        self.assertEqual(self.member.user_id, "TEST-001")
        self.assertTrue(self.member.is_active)
    
    def test_member_str(self):
        """Test member string representation"""
        self.assertEqual(str(self.member), "Test User (TEST-001)")
    
    def test_get_active_devices(self):
        """Test getting active devices"""
        device = Device.objects.create(
            member=self.member,
            device_id=uuid.uuid4(),
            platform='android'
        )
        self.assertEqual(self.member.get_active_devices().count(), 1)
        
        device.logout()
        self.assertEqual(self.member.get_active_devices().count(), 0)


class DeviceModelTests(TestCase):
    """Test Device model functionality"""
    
    def setUp(self):
        self.member = Member.objects.create(
            user_name="Test User",
            user_id="TEST-001"
        )
        self.device_id = uuid.uuid4()
        self.device = Device.objects.create(
            member=self.member,
            device_id=self.device_id,
            platform='android',
            device_name='Test Device'
        )
    
    def test_device_creation(self):
        """Test device is created correctly"""
        self.assertEqual(self.device.member, self.member)
        self.assertEqual(self.device.platform, 'android')
        self.assertFalse(self.device.is_logged_out)
    
    def test_device_logout(self):
        """Test device logout functionality"""
        self.device.last_refresh_token_jti = "test-jti"
        self.device.save()
        
        self.device.logout()
        self.assertTrue(self.device.is_logged_out)
        self.assertIsNone(self.device.last_refresh_token_jti)


class QRLoginTests(APITestCase):
    """Test QR login endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('authentication:qr_login')
        self.member = Member.objects.create(
            user_name="Test User",
            user_id="TEST-001",
            is_active=True
        )
    
    def test_qr_login_success(self):
        """Test successful QR login"""
        data = {
            'user_id': 'TEST-001',
        }
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('user', response.data)
        self.assertIn('expires_in', response.data)
        self.assertEqual(response.data['user']['user_id'], 'TEST-001')
    
    def test_qr_login_with_device_tracking(self):
        """Test QR login with device tracking"""
        device_id = str(uuid.uuid4())
        data = {
            'user_id': 'TEST-001',
            'device_id': device_id,
            'platform': 'android',
            'device_name': 'Test Device'
        }
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('device_id', response.data)
        
        # Verify device was created
        device = Device.objects.get(device_id=device_id)
        self.assertEqual(device.member, self.member)
        self.assertEqual(device.platform, 'android')
        self.assertFalse(device.is_logged_out)
    
    def test_qr_login_invalid_user_id(self):
        """Test QR login with invalid user_id"""
        data = {
            'user_id': 'INVALID-USER',
        }
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_qr_login_inactive_member(self):
        """Test QR login with inactive member"""
        self.member.is_active = False
        self.member.save()
        
        data = {
            'user_id': 'TEST-001',
        }
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_qr_login_missing_user_id(self):
        """Test QR login with missing user_id"""
        data = {}
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TokenRefreshTests(APITestCase):
    """Test token refresh endpoint with rotation"""
    
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('authentication:token_refresh')
        self.member = Member.objects.create(
            user_name="Test User",
            user_id="TEST-001"
        )
        
        # Generate initial tokens
        self.refresh = RefreshToken()
        self.refresh['user_id'] = self.member.id
        self.refresh['user_name'] = self.member.user_name
        self.refresh['member_user_id'] = self.member.user_id
    
    def test_token_refresh_success(self):
        """Test successful token refresh"""
        data = {
            'refresh': str(self.refresh)
        }
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        
        # Verify new tokens are different
        self.assertNotEqual(response.data['refresh'], str(self.refresh))
    
    def test_token_refresh_invalid_token(self):
        """Test token refresh with invalid token"""
        data = {
            'refresh': 'invalid-token'
        }
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_token_refresh_missing_token(self):
        """Test token refresh with missing token"""
        data = {}
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LogoutTests(APITestCase):
    """Test logout endpoint with blacklisting"""
    
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('authentication:logout')
        self.member = Member.objects.create(
            user_name="Test User",
            user_id="TEST-001"
        )
        
        # Generate tokens
        self.refresh = RefreshToken()
        self.refresh['user_id'] = self.member.id
        self.refresh['user_name'] = self.member.user_name
        self.refresh['member_user_id'] = self.member.user_id
        self.access = str(self.refresh.access_token)
    
    def test_logout_success(self):
        """Test successful logout"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')
        
        data = {
            'refresh': str(self.refresh)
        }
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.data)
    
    def test_logout_with_device(self):
        """Test logout with device tracking"""
        device_id = uuid.uuid4()
        device = Device.objects.create(
            member=self.member,
            device_id=device_id,
            platform='android'
        )
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')
        
        data = {
            'refresh': str(self.refresh),
            'device_id': str(device_id)
        }
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify device was logged out
        device.refresh_from_db()
        self.assertTrue(device.is_logged_out)
    
    def test_logout_idempotent(self):
        """Test logout is idempotent"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')
        
        data = {
            'refresh': str(self.refresh)
        }
        
        # First logout
        response1 = self.client.post(self.url, data, format='json')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Second logout (should still return 200)
        response2 = self.client.post(self.url, data, format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
    
    def test_logout_requires_authentication(self):
        """Test logout requires valid access token"""
        data = {
            'refresh': str(self.refresh)
        }
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileTests(APITestCase):
    """Test protected profile endpoint"""
    
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('authentication:profile')
        self.member = Member.objects.create(
            user_name="Test User",
            user_id="TEST-001"
        )
        
        # Generate tokens
        self.refresh = RefreshToken()
        self.refresh['user_id'] = self.member.id
        self.refresh['user_name'] = self.member.user_name
        self.refresh['member_user_id'] = self.member.user_id
        self.access = str(self.refresh.access_token)
    
    def test_profile_success(self):
        """Test successful profile retrieval"""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('member', response.data)
        self.assertIn('devices', response.data)
        self.assertEqual(response.data['member']['user_id'], 'TEST-001')
    
    def test_profile_requires_authentication(self):
        """Test profile requires authentication"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_profile_invalid_token(self):
        """Test profile with invalid token"""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer invalid-token')
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class IntegrationTests(APITestCase):
    """Integration tests for complete authentication flow"""
    
    def setUp(self):
        self.client = APIClient()
        self.member = Member.objects.create(
            user_name="Test User",
            user_id="TEST-001"
        )
    
    def test_complete_authentication_flow(self):
        """Test complete flow: login -> refresh -> profile -> logout"""
        
        # 1. QR Login
        login_data = {
            'user_id': 'TEST-001',
            'device_id': str(uuid.uuid4()),
            'platform': 'android'
        }
        login_response = self.client.post(
            reverse('authentication:qr_login'),
            login_data,
            format='json'
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        
        access_token = login_response.data['access']
        refresh_token = login_response.data['refresh']
        
        # 2. Access Profile
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        profile_response = self.client.get(reverse('authentication:profile'))
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        
        # 3. Refresh Token
        refresh_data = {'refresh': refresh_token}
        refresh_response = self.client.post(
            reverse('authentication:token_refresh'),
            refresh_data,
            format='json'
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        
        new_access = refresh_response.data['access']
        new_refresh = refresh_response.data['refresh']
        
        # 4. Logout
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {new_access}')
        logout_data = {
            'refresh': new_refresh,
            'device_id': login_data['device_id']
        }
        logout_response = self.client.post(
            reverse('authentication:logout'),
            logout_data,
            format='json'
        )
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)
