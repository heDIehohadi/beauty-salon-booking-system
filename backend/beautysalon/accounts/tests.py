import io
from contextlib import redirect_stdout
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from accounts.models import OTPRequest

User = get_user_model()

PASSWORD = "test-password-123"


def make_user(username, phone_number, **extra):
    # phone_number یکتاست و default ندارد؛ همیشه صریح می‌دهیم.
    return User.objects.create_user(
        username=username,
        password=PASSWORD,
        phone_number=phone_number,
        **extra,
    )


class RegistrationTests(APITestCase):
    def payload(self, **overrides):
        data = {
            "username": "newuser",
            "phone_number": "09121111111",
            "password": PASSWORD,
            "password_confirm": PASSWORD,
        }
        data.update(overrides)
        return data

    def test_register_creates_unverified_customer(self):
        response = self.client.post(reverse("register"), self.payload())

        self.assertEqual(
            response.status_code, status.HTTP_201_CREATED, response.data
        )
        user = User.objects.get(username="newuser")
        self.assertFalse(user.is_phone_verified)
        self.assertEqual(user.role, User.Role.CUSTOMER)

    def test_password_is_stored_hashed_and_not_returned(self):
        response = self.client.post(reverse("register"), self.payload())

        self.assertNotIn("password", response.data)
        self.assertNotIn("password_confirm", response.data)
        user = User.objects.get(username="newuser")
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))

    def test_role_cannot_be_chosen_at_registration(self):
        # جلوگیری از privilege escalation: کاربر نباید خودش admin شود.
        self.client.post(
            reverse("register"),
            self.payload(role="admin", is_staff=True, is_superuser=True),
        )

        user = User.objects.get(username="newuser")
        self.assertEqual(user.role, User.Role.CUSTOMER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_password_mismatch_is_rejected(self):
        response = self.client.post(
            reverse("register"),
            self.payload(password_confirm="different-password-1"),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_short_password_is_rejected(self):
        response = self.client.post(
            reverse("register"),
            self.payload(password="short", password_confirm="short"),
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_phone_number_is_rejected(self):
        make_user("existing", "09121111111")

        response = self.client.post(reverse("register"), self.payload())

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 1)


class LoginTests(APITestCase):
    def login(self, username="loginuser", password=PASSWORD):
        return self.client.post(
            reverse("login"),
            {"username": username, "password": password},
        )

    def test_verified_user_gets_token(self):
        user = make_user(
            "loginuser", "09122222222", is_phone_verified=True
        )

        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["token"], Token.objects.get(user=user).key
        )

    def test_unverified_user_cannot_login(self):
        make_user("loginuser", "09122222222", is_phone_verified=False)

        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Token.objects.exists())

    def test_wrong_password_is_rejected(self):
        make_user("loginuser", "09122222222", is_phone_verified=True)

        response = self.login(password="wrong-password-1")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_user_is_rejected(self):
        response = self.login(username="nobody")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_inactive_user_cannot_login(self):
        make_user(
            "loginuser",
            "09122222222",
            is_phone_verified=True,
            is_active=False,
        )

        response = self.login()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RequestOTPTests(APITestCase):
    def setUp(self):
        self.user = make_user("otpuser", "09123333333")

    def request_otp(self, phone_number="09123333333"):
        # کد OTP در حالت development چاپ می‌شود؛ خروجی را بی‌صدا می‌کنیم.
        with redirect_stdout(io.StringIO()):
            return self.client.post(
                reverse("request-otp"), {"phone_number": phone_number}
            )

    def test_unknown_phone_returns_404(self):
        response = self.request_otp("09129999999")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_already_verified_phone_returns_400(self):
        self.user.is_phone_verified = True
        self.user.save()

        response = self.request_otp()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(OTPRequest.objects.exists())

    def test_otp_is_created_hashed_with_five_minute_expiry(self):
        with mock.patch("accounts.views.secrets.randbelow", return_value=123456):
            response = self.request_otp()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        otp = OTPRequest.objects.get()
        self.assertNotEqual(otp.otp_code, "123456")
        self.assertFalse(otp.is_used)
        remaining = otp.expires_at - timezone.now()
        self.assertGreater(remaining, timedelta(minutes=4))
        self.assertLessEqual(remaining, timedelta(minutes=5))

    def test_response_does_not_leak_the_code(self):
        with mock.patch("accounts.views.secrets.randbelow", return_value=123456):
            response = self.request_otp()

        self.assertNotIn("123456", str(response.data))

    def test_second_request_within_60_seconds_is_rate_limited(self):
        self.request_otp()

        response = self.request_otp()

        self.assertEqual(
            response.status_code, status.HTTP_429_TOO_MANY_REQUESTS
        )
        self.assertEqual(OTPRequest.objects.count(), 1)

    def test_new_request_after_60_seconds_invalidates_previous_otp(self):
        self.request_otp()
        OTPRequest.objects.update(
            created_at=timezone.now() - timedelta(seconds=61)
        )

        response = self.request_otp()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(OTPRequest.objects.filter(is_used=False).count(), 1)
        self.assertEqual(OTPRequest.objects.filter(is_used=True).count(), 1)


class VerifyOTPTests(APITestCase):
    CODE = "123456"

    def setUp(self):
        self.user = make_user("verifyuser", "09124444444")
        self.otp = OTPRequest.objects.create(
            user=self.user,
            otp_code=make_password(self.CODE),
            expires_at=timezone.now() + timedelta(minutes=5),
        )

    def verify(self, code=None, phone_number="09124444444"):
        return self.client.post(
            reverse("verify-otp"),
            {"phone_number": phone_number, "code": code or self.CODE},
        )

    def test_correct_code_verifies_phone(self):
        response = self.verify()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.otp.refresh_from_db()
        self.assertTrue(self.user.is_phone_verified)
        self.assertTrue(self.otp.is_used)

    def test_user_can_login_after_verification(self):
        self.verify()

        response = self.client.post(
            reverse("login"),
            {"username": "verifyuser", "password": PASSWORD},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_wrong_code_is_rejected_and_counts_an_attempt(self):
        response = self.verify(code="654321")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.otp.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.otp.attempts, 1)
        self.assertFalse(self.otp.is_used)
        self.assertFalse(self.user.is_phone_verified)

    def test_code_must_be_exactly_six_digits(self):
        for bad_code in ("12345", "1234567", "abcdef"):
            with self.subTest(code=bad_code):
                response = self.verify(code=bad_code)

                self.assertEqual(
                    response.status_code, status.HTTP_400_BAD_REQUEST
                )

    def test_expired_code_is_rejected(self):
        OTPRequest.objects.update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

        response = self.verify()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_phone_verified)

    def test_code_is_blocked_after_five_wrong_attempts(self):
        # brute-force یک کد ۶ رقمی باید با محدودیت تعداد تلاش بسته شود.
        for _ in range(5):
            self.verify(code="654321")

        response = self.verify()  # حالا کد درست هم قبول نمی‌شود.

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_phone_verified)

    def test_used_code_cannot_be_reused(self):
        self.verify()
        self.user.is_phone_verified = False
        self.user.save()

        response = self.verify()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_phone_returns_generic_400(self):
        response = self.verify(phone_number="09120000000")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_already_verified_phone_returns_400(self):
        self.user.is_phone_verified = True
        self.user.save()

        response = self.verify()

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ProfileTests(APITestCase):
    def test_profile_requires_authentication(self):
        response = self.client.get(reverse("profile"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_returns_current_user_only(self):
        user = make_user("profileuser", "09125555555", is_phone_verified=True)
        make_user("someoneelse", "09125555556")
        token = Token.objects.create(user=user)

        response = self.client.get(
            reverse("profile"), HTTP_AUTHORIZATION=f"Token {token.key}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "profileuser")
        self.assertEqual(response.data["phone_number"], "09125555555")
        self.assertTrue(response.data["is_phone_verified"])
        self.assertNotIn("password", response.data)


class IsSalonAdminPermissionTests(APITestCase):
    """IsSalonAdmin protects the admin booking list endpoint."""

    def test_anonymous_is_rejected(self):
        response = self.client.get(reverse("admin-booking-list"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_customer_is_forbidden(self):
        customer = make_user("customer", "09126666661")
        self.client.force_authenticate(user=customer)

        response = self.client.get(reverse("admin-booking-list"))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_salon_admin_is_allowed(self):
        admin = make_user("salonadmin", "09126666662", role=User.Role.ADMIN)
        self.client.force_authenticate(user=admin)

        response = self.client.get(reverse("admin-booking-list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
