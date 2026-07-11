# user_service/users/views.py

import secrets

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.conf import settings
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    UserRegistrationSerializer,
    EmailVerificationSerializer,
    UserLoginSerializer,
    UserSerializer,
    PasswordChangeSerializer,
    PasswordResetSerializer,
)
from .models import EmailVerification, PasswordReset

User = get_user_model()


def generate_otp():
    """Cryptographically secure 6-digit code."""
    return f"{secrets.randbelow(10**6):06d}"


def issue_otp(user, model, subject, body_template):
    """Create a hashed OTP record and email the plain code to the user."""
    otp = generate_otp()
    model.objects.create(user=user, otp=make_password(otp))
    send_mail(
        subject,
        body_template.format(otp=otp),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


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


class UserLoginView(APIView):
    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'login'

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_200_OK)


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
