from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Used for /register/."""
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class EmailVerificationSerializer(serializers.Serializer):
    """Used for /verify-email/."""
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)


class ResendOTPSerializer(serializers.Serializer):
    """Used for /resend-otp/."""
    email = serializers.EmailField()


class LogoutSerializer(serializers.Serializer):
    """Used for /logout/."""
    refresh = serializers.CharField()


class UserLoginSerializer(serializers.Serializer):
    """Used for /login/. Validates credentials and email verification."""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data['username'], password=data['password'])
        if user is None:
            raise serializers.ValidationError('Invalid credentials.')
        if not user.email_verified:
            raise serializers.ValidationError('Email is not verified.')
        data['user'] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    """Used for /me/ and /me/update/."""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'email_verified']
        read_only_fields = ['id', 'email_verified']


class PasswordChangeSerializer(serializers.Serializer):
    """Used for /me/change-password/."""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])


class PasswordResetSerializer(serializers.Serializer):
    """Used for /reset-password/."""
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
