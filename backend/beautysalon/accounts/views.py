import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import OTPRequest
from .serializers import (
    LoginSerializer,
    RegistrationSerializer,
    RequestOTPSerializer,
    VerifyOTPSerializer,
)
from rest_framework.permissions import IsAuthenticated
User = get_user_model()


class RegistrationView(generics.CreateAPIView):
    serializer_class = RegistrationSerializer
    permission_classes = [AllowAny]


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "message": "Login successful.",
                "token": token.key,
            },
            status=status.HTTP_200_OK,
        )


class RequestOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        user = User.objects.filter(phone_number=phone_number).first()

        if user is None:
            return Response(
                {"detail": "No account found for this phone number."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if user.is_phone_verified:
            return Response(
                {"detail": "Phone number is already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        now = timezone.now()
        latest_otp = OTPRequest.objects.filter(user=user).first()

        if (
            latest_otp
            and now - latest_otp.created_at < timedelta(seconds=60)
        ):
            return Response(
                {"detail": "Please wait before requesting another OTP."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        OTPRequest.objects.filter(
            user=user,
            is_used=False,
        ).update(is_used=True)

        code = f"{secrets.randbelow(1_000_000):06d}"

        OTPRequest.objects.create(
            user=user,
            otp_code=make_password(code),
            expires_at=now + timedelta(minutes=5),
        )

        # Development only. Replace with an SMS provider before production.
        print(f"Development OTP for {phone_number}: {code}")

        return Response(
            {
                "message": "If the account is eligible, an OTP has been generated."
            },
            status=status.HTTP_200_OK,
        )


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        submitted_otp = serializer.validated_data["code"]

        user = User.objects.filter(phone_number=phone_number).first()

        if user is None:
            return Response(
                {"detail": "Invalid or expired OTP."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.is_phone_verified:
            return Response(
                {"detail": "Phone number is already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            otp_request = (
                OTPRequest.objects.select_for_update()
                .filter(user=user, is_used=False)
                .order_by("-created_at")
                .first()
            )

            if (
                otp_request is None
                or otp_request.expires_at <= timezone.now()
            ):
                return Response(
                    {"detail": "Invalid or expired OTP."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if otp_request.attempts >= 5:
                otp_request.is_used = True
                otp_request.save(update_fields=["is_used"])

                return Response(
                    {"detail": "Too many attempts. Request a new OTP."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            otp_request.attempts += 1

            if not check_password(
                submitted_otp,
                otp_request.otp_code,
            ):
                otp_request.save(update_fields=["attempts"])

                return Response(
                    {"detail": "Invalid or expired OTP."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            otp_request.is_used = True
            otp_request.save(update_fields=["attempts", "is_used"])

            user.is_phone_verified = True
            user.save(update_fields=["is_phone_verified"])

        return Response(
            {"message": "Phone number verified successfully."},
            status=status.HTTP_200_OK,
        )

class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "id": request.user.id,
            "username": request.user.username,
            "phone_number": request.user.phone_number,
            "is_phone_verified": request.user.is_phone_verified,
        })   