"""Settings for pytest: sqlite, in-memory email, ephemeral RS256 keys."""
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from user_service.settings import *  # noqa: F401,F403

DATABASES = {
    'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}
}
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']  # test speed
CELERY_TASK_ALWAYS_EAGER = True  # run .delay() inline; no broker in tests

# Generous rates so ordinary tests never trip throttling; the dedicated
# throttle test patches rates down explicitly.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    'DEFAULT_THROTTLE_RATES': {'otp': '1000/hour', 'login': '1000/min'},
}

# Ephemeral RS256 keypair so tests do not depend on files on disk.
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
    'SIGNING_KEY': TEST_JWT_PRIVATE_KEY,
    'VERIFYING_KEY': TEST_JWT_PUBLIC_KEY,
}
