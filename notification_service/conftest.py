from datetime import datetime, timedelta, timezone

import jwt
import pytest
from django.conf import settings
from rest_framework.test import APIClient


def make_token(user_id=1, username='alice'):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            'token_type': 'access',
            'exp': now + timedelta(minutes=15),
            'iat': now,
            'jti': f'test-{user_id}',
            'user_id': user_id,
            'username': username,
            'email': f'{username}@example.com',
        },
        settings.TEST_JWT_PRIVATE_KEY,
        algorithm='RS256',
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def auth_client():
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {make_token()}')
    return client
