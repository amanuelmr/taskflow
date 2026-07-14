# notification_service/notifications/authentication.py

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class CustomJWTAuthentication(JWTAuthentication):
    """
    Verify-only JWT authentication: tokens are issued by the user service
    and validated here with the RS256 public key. There is no local user
    table, so request.user is a lightweight object built from claims.
    """

    def get_user(self, validated_token):
        try:
            user_id = validated_token["user_id"]
            username = validated_token.get("username", "Unknown")
            email = validated_token.get("email", "unknown@example.com")
        except KeyError:
            raise InvalidToken("Token contained no recognizable user identification")

        class SimpleUser:
            is_authenticated = True
            is_anonymous = False
            is_active = True

            def __init__(self, id, username, email):
                self.id = id
                self.pk = id  # DRF throttling identifies users by .pk
                self.username = username
                self.email = email

            def __str__(self):
                return self.username

        return SimpleUser(id=user_id, username=username, email=email)
