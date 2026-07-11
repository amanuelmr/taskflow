from datetime import datetime, timedelta, timezone

import jwt
import pytest
from django.conf import settings
from rest_framework.test import APIClient


def make_token(user_id, username='user', key=None, algorithm='RS256'):
    """Mint an access token the way the user service would."""
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
        key or settings.TEST_JWT_PRIVATE_KEY,
        algorithm=algorithm,
    )


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def alice():
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {make_token(1, "alice")}')
    return client


@pytest.fixture
def bob():
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {make_token(2, "bob")}')
    return client


@pytest.fixture(autouse=True)
def _mock_publish(monkeypatch):
    """Capture events instead of enqueueing them on RabbitMQ."""
    events = []

    def fake_publish(exchange_name, routing_key, message_body):
        events.append(
            {'exchange': exchange_name, 'routing_key': routing_key, 'body': message_body}
        )

    monkeypatch.setattr('tasks.views.publish_event', fake_publish)
    # Tests run inside a transaction that never commits, so run on_commit
    # callbacks immediately to observe published events.
    monkeypatch.setattr('django.db.transaction.on_commit', lambda fn, using=None: fn())
    return events


@pytest.fixture
def published(_mock_publish):
    return _mock_publish
