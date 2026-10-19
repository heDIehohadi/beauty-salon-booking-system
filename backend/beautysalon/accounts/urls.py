from django.urls import path

from .views import (
    LoginView,
    RegistrationView,
    RequestOTPView,
    VerifyOTPView,
    ProfileView
)

urlpatterns = [
    path("register/", RegistrationView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("otp/request/", RequestOTPView.as_view(), name="request-otp"),
    path("otp/verify/", VerifyOTPView.as_view(), name="verify-otp"),
    path("profile/", ProfileView.as_view(), name="profile"),
]