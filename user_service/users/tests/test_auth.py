import re

import jwt
import pytest
from conftest import PASSWORD
from django.conf import settings
from django.core import mail
from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle

from users.models import EmailVerification, PasswordReset, User

pytestmark = pytest.mark.django_db

REGISTRATION = {'username': 'bob', 'email': 'bob@example.com', 'password': PASSWORD}


def latest_otp():
    """Extract the OTP from the most recent email."""
    return re.search(r'\b(\d{6})\b', mail.outbox[-1].body).group(1)


def register(api_client, **overrides):
    return api_client.post('/api/register/', {**REGISTRATION, **overrides})


class TestRegistration:
    def test_register_creates_user_with_hashed_otp(self, api_client):
        response = register(api_client)
        assert response.status_code == 201
        user = User.objects.get(username='bob')
        assert not user.email_verified
        verification = EmailVerification.objects.get(user=user)
        assert len(mail.outbox) == 1
        assert latest_otp() not in verification.otp  # stored hashed, not plaintext

    def test_register_rejects_weak_password(self, api_client):
        response = register(api_client, password='123')
        assert response.status_code == 400
        assert not User.objects.filter(username='bob').exists()

    def test_register_rejects_duplicate_email(self, api_client, user):
        response = register(api_client, email=user.email)
        assert response.status_code == 400


class TestEmailVerification:
    def test_verify_happy_path(self, api_client):
        register(api_client)
        response = api_client.post(
            '/api/verify-email/', {'email': 'bob@example.com', 'otp': latest_otp()}
        )
        assert response.status_code == 200
        assert User.objects.get(username='bob').email_verified

    def test_wrong_otp_rejected(self, api_client):
        register(api_client)
        response = api_client.post(
            '/api/verify-email/', {'email': 'bob@example.com', 'otp': '000000'}
        )
        assert response.status_code == 400

    def test_expired_otp_rejected(self, api_client):
        register(api_client)
        EmailVerification.objects.update(expires_at=timezone.now() - timezone.timedelta(minutes=1))
        response = api_client.post(
            '/api/verify-email/', {'email': 'bob@example.com', 'otp': latest_otp()}
        )
        assert response.status_code == 400

    def test_otp_single_use(self, api_client):
        register(api_client)
        otp = latest_otp()
        assert api_client.post(
            '/api/verify-email/', {'email': 'bob@example.com', 'otp': otp}
        ).status_code == 200
        assert api_client.post(
            '/api/verify-email/', {'email': 'bob@example.com', 'otp': otp}
        ).status_code == 400


class TestLogin:
    def test_unverified_user_cannot_login(self, api_client):
        register(api_client)
        response = api_client.post(
            '/api/login/', {'username': 'bob', 'password': PASSWORD}
        )
        assert response.status_code == 400

    def test_login_returns_rs256_token_with_claims(self, api_client, user):
        response = api_client.post(
            '/api/login/', {'username': user.username, 'password': PASSWORD}
        )
        assert response.status_code == 200
        access = response.data['access']
        assert jwt.get_unverified_header(access)['alg'] == 'RS256'
        claims = jwt.decode(
            access, settings.TEST_JWT_PUBLIC_KEY, algorithms=['RS256']
        )
        assert claims['username'] == user.username
        assert claims['email'] == user.email
        assert claims['email_verified'] is True

    def test_bad_credentials_generic_error(self, api_client, user):
        response = api_client.post(
            '/api/login/', {'username': user.username, 'password': 'wrong'}
        )
        assert response.status_code == 400
        assert user.username not in str(response.data.get('non_field_errors', ''))


class TestProfile:
    def test_me_requires_auth(self, api_client):
        assert api_client.get('/api/me/').status_code == 401

    def test_me_returns_profile(self, api_client, user):
        api_client.force_authenticate(user)
        response = api_client.get('/api/me/')
        assert response.status_code == 200
        assert response.data['email_verified'] is True


class TestPasswordChange:
    def test_wrong_old_password(self, api_client, user):
        api_client.force_authenticate(user)
        response = api_client.put(
            '/api/me/change-password/',
            {'old_password': 'wrong', 'new_password': 'An0ther-Passw0rd!'},
        )
        assert response.status_code == 400

    def test_change_password_flow(self, api_client, user):
        api_client.force_authenticate(user)
        response = api_client.put(
            '/api/me/change-password/',
            {'old_password': PASSWORD, 'new_password': 'An0ther-Passw0rd!'},
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.check_password('An0ther-Passw0rd!')


class TestPasswordReset:
    def test_forgot_password_uniform_response(self, api_client, user):
        unknown = api_client.post('/api/forgot-password/', {'email': 'nobody@example.com'})
        known = api_client.post('/api/forgot-password/', {'email': user.email})
        assert unknown.status_code == known.status_code == 200
        assert unknown.data == known.data
        assert len(mail.outbox) == 1  # only the real account got an email

    def test_reset_password_flow(self, api_client, user):
        api_client.post('/api/forgot-password/', {'email': user.email})
        response = api_client.post(
            '/api/reset-password/',
            {'email': user.email, 'otp': latest_otp(), 'new_password': 'An0ther-Passw0rd!'},
        )
        assert response.status_code == 200
        user.refresh_from_db()
        assert user.check_password('An0ther-Passw0rd!')
        assert not PasswordReset.objects.filter(user=user).exists()  # single use


class TestThrottling:
    def test_otp_endpoints_throttle(self, api_client, monkeypatch):
        monkeypatch.setitem(ScopedRateThrottle.THROTTLE_RATES, 'otp', '2/hour')
        api_client.post('/api/forgot-password/', {'email': 'x@example.com'})
        api_client.post('/api/forgot-password/', {'email': 'x@example.com'})
        response = api_client.post('/api/forgot-password/', {'email': 'x@example.com'})
        assert response.status_code == 429
