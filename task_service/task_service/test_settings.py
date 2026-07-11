"""Settings for pytest: sqlite, ephemeral RS256 keys, eager Celery."""
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from task_service.settings import *  # noqa: F401,F403

DATABASES = {
    'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}
}
CELERY_TASK_ALWAYS_EAGER = True

REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    'DEFAULT_THROTTLE_RATES': {'anon': '1000/min', 'user': '1000/min'},
}

# Ephemeral RS256 keypair; the private half lets tests mint tokens the way
# the user service would.
_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TEST_JWT_PRIVATE_KEY = _key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
TEST_JWT_PUBLIC_KEY = _key.public_key().public_bytes(
    serialization.Encoding.PEM,
    serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()

SIMPLE_JWT = {
    'AUTH_HEADER_TYPES': ('Bearer',),
    'ALGORITHM': 'RS256',
    'SIGNING_KEY': None,
    'VERIFYING_KEY': TEST_JWT_PUBLIC_KEY,
}
