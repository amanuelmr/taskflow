import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

PASSWORD = 'Str0ng-Passw0rd!'


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    u = User.objects.create_user(
        username='alice', email='alice@example.com', password=PASSWORD
    )
    u.email_verified = True
    u.save(update_fields=['email_verified'])
    return u
