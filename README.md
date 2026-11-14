# Beauty Salon Booking System

[![CI](https://github.com/heDIehohadi/beauty-salon-booking-system/actions/workflows/ci.yml/badge.svg)](https://github.com/heDIehohadi/beauty-salon-booking-system/actions/workflows/ci.yml)

A REST API for a beauty salon appointment booking workflow, built with
Django and Django REST Framework. Customers can browse services and
stylists, see free time slots that respect each service's duration, and
book, view and cancel appointments. Salon administrators manage stylists,
working hours, breaks and leave.

The problem statement and scope are in
[`docs/01-problem-definition.md`](docs/01-problem-definition.md).

## Features

- Custom user model (`accounts.User`) with unique phone number and a
  `customer` / `admin` role.
- Registration, token login and phone verification with a one-time code
  (code is hashed, expires after 5 minutes, 60-second resend limit,
  locked after 5 wrong attempts).
- Public service catalog with category filter.
- Public stylist catalog (active stylists, their active services,
  portfolio and active working hours).
- Available slots in 15-minute steps, based on the stylist's working
  hours, the service duration, existing bookings and stylist time off.
- Booking creation with server-side validation: future time only,
  stylist must offer the service, fits inside working hours, no overlap
  with other bookings, no overlap with time off, no crossing midnight.
- Customers only see, cancel and reschedule their own bookings.
- Admin-only list of all bookings; working hours, time off and bookings
  are also manageable in Django Admin.

## Tech stack

Python, Django 6.1, Django REST Framework (token authentication),
SQLite (development), Pillow (image fields), Ruff (linting).
Time zone: `Asia/Tehran`, `USE_TZ = True`.

## Project layout

```
backend/
  requirements.txt, requirements-dev.txt
  beautysalon/            # Django project root (manage.py)
    accounts/             # user model, registration, OTP, token login
    services/             # service catalog
    stylists/             # stylists, working hours, time off, public API
    booking/              # bookings, slots, cancel, reschedule, seed_demo
docs/                     # project documents
```

## Getting started

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements-dev.txt

cd backend/beautysalon
python manage.py migrate
python manage.py createsuperuser   # phone_number is required and unique
python manage.py runserver
```

Run the checks:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
ruff check .
python manage.py test
```

## Quick demo

`seed_demo` creates two users (`demo_admin` and `demo_customer`, both with
the password `demo-pass-12345`; demo data only), six services, three
stylists with working hours and one leave day. It is safe to run twice.

```bash
cd backend/beautysalon
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

In a second terminal (use a Monday date in the future for `DATE`):

```bash
API=http://127.0.0.1:8000/api
DATE=2026-11-16

# 1. Log in and keep the token
TOKEN=$(curl -s -X POST $API/accounts/login/ \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo_customer","password":"demo-pass-12345"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 2. Browse the catalog (public)
curl -s $API/services/
curl -s $API/stylists/

# 3. Free slots for stylist 1 and service 3 (Haircut)
curl -s -H "Authorization: Token $TOKEN" \
  "$API/bookings/available-slots/?stylist=1&service=3&date=$DATE"

# 4. Book 10:00, move it to 11:00, then cancel it
curl -s -X POST -H "Authorization: Token $TOKEN" \
  -H 'Content-Type: application/json' $API/bookings/ \
  -d "{\"service\":3,\"stylist\":1,\"start_at\":\"${DATE}T10:00:00+03:30\"}"
curl -s -X PATCH -H "Authorization: Token $TOKEN" \
  -H 'Content-Type: application/json' $API/bookings/1/reschedule/ \
  -d "{\"start_at\":\"${DATE}T11:00:00+03:30\"}"
curl -s -X PATCH -H "Authorization: Token $TOKEN" $API/bookings/1/cancel/
```

Booking 10:30 right after a 10:00 haircut, or 14:00 during the stylist's
lunch break, is rejected with HTTP 400. `demo_admin` can also open
`/admin/` and `GET /api/bookings/admin/`.

## Configuration

Settings are read from environment variables; without any of them the
project runs in development mode. Copy `backend/beautysalon/.env.example`
and load it with `set -a; source .env; set +a` (Django does not read
`.env` files by itself).

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_DEBUG` | `true` | Set to `false` in production |
| `DJANGO_SECRET_KEY` | built-in insecure key (only when debug is on) | Required when `DJANGO_DEBUG=false`, otherwise startup fails |
| `DJANGO_ALLOWED_HOSTS` | empty | Comma-separated host names |

Uploaded images are stored in `backend/beautysalon/media/` and served by
Django only while `DJANGO_DEBUG` is on; in production a web server or
object storage must serve `MEDIA_ROOT`.

## API overview

All endpoints are under `/api/`. Authenticated endpoints expect the header
`Authorization: Token <token>`.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/accounts/register/` | public | Create a customer (`username`, `phone_number`, `password`, `password_confirm`) |
| POST | `/api/accounts/otp/request/` | public | Generate a verification code for a phone number |
| POST | `/api/accounts/otp/verify/` | public | Verify the phone number (`phone_number`, 6-digit `code`) |
| POST | `/api/accounts/login/` | public | Returns `token` (phone must be verified) |
| GET | `/api/accounts/profile/` | user | Current user |
| GET | `/api/services/` | public | Active services, optional `?category=` |
| GET | `/api/services/<id>/` | public | Service detail |
| GET | `/api/stylists/` | public | Active stylists with their active services |
| GET | `/api/stylists/<id>/` | public | Stylist detail with portfolio and active working hours |
| GET | `/api/bookings/available-slots/?stylist=&service=&date=YYYY-MM-DD` | user | Free start times |
| GET, POST | `/api/bookings/` | user | List own bookings / create a booking |
| GET | `/api/bookings/<id>/` | user | Own booking detail |
| PATCH | `/api/bookings/<id>/cancel/` | user | Cancel an own booking (pending or confirmed only) |
| PATCH | `/api/bookings/<id>/reschedule/` | user | Move an own booking to a new `start_at` |
| GET | `/api/bookings/admin/` | admin | All bookings |

## Business rules

- Slot start times are generated every 15 minutes; a slot is offered only
  if the whole service duration fits inside an active working hour.
- A slot is hidden if it overlaps a pending or confirmed booking or an
  active time-off period of the stylist.
- A booking that is already cancelled or completed cannot be cancelled.
- Rescheduling changes only `start_at`; the service and stylist stay the same.
  The new time must pass every rule of a new booking (the booking being
  moved is ignored in the overlap check). Only pending or confirmed bookings
  that have not started yet can be moved. A minimum-notice rule is not
  defined yet.
- Working hours of one stylist on one weekday may not overlap
  (validated in `clean()`, so in Django Admin and forms; a plain
  `save()` does not call `clean()`).

## Known limitations

- No real SMS provider: in development the verification code is printed
  to the server console.
- Concurrency: the booking view locks the stylist row with
  `select_for_update`, which has an effect on PostgreSQL but not on
  SQLite. Production use needs PostgreSQL and a database-level guarantee
  against double booking.
- Production deployment is not set up (no Docker, no PostgreSQL
  configuration, no web server); see "Configuration" for the environment
  variables that already exist.
