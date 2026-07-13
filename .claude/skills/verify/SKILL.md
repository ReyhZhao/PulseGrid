---
name: verify
description: Launch PulseGrid locally (isolated from docker-compose and other stacks) and drive the API surface to verify changes at runtime.
---

# Verifying PulseGrid at runtime

Isolated stack without docker-compose (host port 8000 is often taken by the
Vels.online stack; its valkey is not host-exposed):

```bash
# 1. Scratch redis (queues are required for channel/audit/alert writes)
docker run -d --rm --name pulsegrid-verify-valkey -p 127.0.0.1:6399:6379 valkey/valkey:8-alpine

# 2. Env for every controlplane process (scratch sqlite, auto-login)
export DJANGO_DEBUG=1 DEV_AUTO_LOGIN=1 \
  REDIS_URL=redis://127.0.0.1:6399/0 \
  DATABASE_URL="sqlite:///$SCRATCH/verify.sqlite3" \
  DJANGO_SUPERUSER_USERNAME=admin DJANGO_SUPERUSER_EMAIL=admin@localhost DJANGO_SUPERUSER_PASSWORD=admin

cd controlplane
.venv/bin/python manage.py migrate && .venv/bin/python manage.py ensure_regions && .venv/bin/python manage.py createsuperuser --noinput
.venv/bin/python manage.py runserver 127.0.0.1:8100 --noreload   # web
.venv/bin/python manage.py rundispatcher                          # notifications (separate process)
```

Driving the session-authenticated API with curl (DEV_AUTO_LOGIN authenticates
every request as the superuser, but CSRF is still enforced on unsafe methods):

```bash
J=cookies.txt
CSRF=$(curl -s -c $J -b $J http://127.0.0.1:8100/api/v1/auth/csrf | python3 -c 'import sys,json;print(json.load(sys.stdin)["csrftoken"])')
curl -s -b $J -X POST http://127.0.0.1:8100/api/v1/... \
  -H "Content-Type: application/json" -H "X-CSRFToken: $CSRF" -H "Referer: http://127.0.0.1:8100/" -d '{...}'
```

Gotchas:

- `/api/v1/me` gives the org id needed for creating monitors/channels.
- Alert lifecycle: `manage.py shell -c "...services.open_event(monitor, 'down', ...)"`
  enqueues to redis; the *dispatcher* process performs delivery — watch its log.
- Web push (VAPID): generate keys with `manage.py generate_vapid_keys` and export
  them; a stub push service (HTTP server returning 201) works as a subscription
  endpoint, but `p256dh` must be a real P-256 public key (generate with
  `cryptography`) or pywebpush fails encrypting.
- Tear down: pkill the manage.py processes, `docker stop pulsegrid-verify-valkey`.
