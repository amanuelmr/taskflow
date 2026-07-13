# user_service/users/views.py

import logging
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import transaction
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmailVerification, PasswordReset
from .rabbitmq_utils import publish_event
from .serializers import (
    EmailVerificationSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
    ResendOTPSerializer,
    UserLoginSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)
from .tasks import send_email_task

User = get_user_model()

logger = logging.getLogger(__name__)


def generate_otp():
    """Cryptographically secure 6-digit code."""
    return f"{secrets.randbelow(10**6):06d}"


def tokens_for_user(user):
    """Issue a refresh/access pair carrying the claims the other services
    read (they have no user database of their own)."""
    refresh = RefreshToken.for_user(user)
    refresh['username'] = user.username
    refresh['email'] = user.email
    refresh['email_verified'] = user.email_verified
    return {'refresh': str(refresh), 'access': str(refresh.access_token)}


def issue_otp(user, model, subject, body_template):
    """Create a hashed OTP record and email the plain code to the user.
    Sending goes through Celery; falls back to synchronous send_mail when
    the broker is unreachable so the user still gets their code."""
    otp = generate_otp()
    model.objects.create(user=user, otp=make_password(otp))
    message = body_template.format(otp=otp)
    try:
        send_email_task.delay(subject, message, user.email)
    except Exception:
        logger.exception('Celery enqueue failed; sending OTP email synchronously')
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email],
                  fail_silently=False)


class UserRegistrationView(generics.CreateAPIView):
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'otp'

    def perform_create(self, serializer):
        user = serializer.save()
        issue_otp(
            user,
            EmailVerification,
            'Verify your email',
            'Your OTP for email verification is {otp}',
        )
        payload = {'user_id': user.id, 'username': user.username, 'email': user.email}
        transaction.on_commit(
            lambda: publish_event('user_events', 'user_registered', payload)
        )


class EmailVerificationView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'otp'

    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']

        error = Response({'detail': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(email=email)
            verification = EmailVerification.objects.filter(user=user).latest('created_at')
        except (User.DoesNotExist, EmailVerification.DoesNotExist):
            return error

        if verification.is_expired() or not check_password(otp, verification.otp):
            return error

        user.email_verified = True
        user.save(update_fields=['email_verified'])
        verification.delete()  # Remove used OTP
        return Response({'detail': 'Email verified successfully.'}, status=status.HTTP_200_OK)


class ResendOTPView(APIView):
    """Re-issue an email-verification OTP. The verification code expires, so
    without this a new user whose code lapses could never verify or log in."""
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'otp'

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        # Uniform response regardless of whether the account exists or is
        # already verified, to prevent user enumeration.
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            user = None
        if user is not None and not user.email_verified:
            EmailVerification.objects.filter(user=user).delete()
            issue_otp(
                user,
                EmailVerification,
                'Verify your email',
                'Your OTP for email verification is {otp}',
            )
        return Response(
            {'detail': 'If that email exists and is unverified, a code has been sent.'},
            status=status.HTTP_200_OK,
        )


class UserLoginView(APIView):
    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'login'

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        return Response(tokens_for_user(user), status=status.HTTP_200_OK)


class LogoutView(APIView):
    """Revoke a refresh token by blacklisting it."""
    serializer_class = LogoutSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data['refresh']).blacklist()
        except TokenError:
            return Response(
                {'detail': 'Invalid or expired refresh token.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_205_RESET_CONTENT)


class UserDetailView(generics.RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class UserUpdateView(generics.UpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class PasswordChangeView(APIView):
    serializer_class = PasswordChangeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user
        old_password = serializer.validated_data['old_password']
        new_password = serializer.validated_data['new_password']

        if not user.check_password(old_password):
            return Response({'detail': 'Wrong password.'}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({'detail': 'Password updated successfully.'}, status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'otp'

    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'detail': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Uniform response whether or not the account exists, to prevent
        # user enumeration.
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            pass
        else:
            issue_otp(
                user,
                PasswordReset,
                'Password Reset OTP',
                'Your OTP for password reset is {otp}',
            )
        return Response(
            {'detail': 'If that email exists, an OTP has been sent.'},
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    serializer_class = PasswordResetSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'otp'

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        otp = serializer.validated_data['otp']
        new_password = serializer.validated_data['new_password']

        error = Response({'detail': 'Invalid or expired OTP.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            user = User.objects.get(email=email)
            reset = PasswordReset.objects.filter(user=user).latest('created_at')
        except (User.DoesNotExist, PasswordReset.DoesNotExist):
            return error

        if reset.is_expired() or not check_password(otp, reset.otp):
            return error

        user.set_password(new_password)
        user.save()
        reset.delete()  # Remove used OTP
        return Response({'detail': 'Password reset successfully.'}, status=status.HTTP_200_OK)
