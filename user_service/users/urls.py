from django.urls import path

from .views import (
    EmailVerificationView,
    ForgotPasswordView,
    LogoutView,
    PasswordChangeView,
    ResendOTPView,
    ResetPasswordView,
    UserDetailView,
    UserLoginView,
    UserRegistrationView,
    UserUpdateView,
)

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('verify-email/', EmailVerificationView.as_view(), name='verify-email'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend-otp'),
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('me/', UserDetailView.as_view(), name='user-detail'),
    path('me/update/', UserUpdateView.as_view(), name='user-update'),
    path('me/change-password/', PasswordChangeView.as_view(), name='change-password'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset-password'),
]
