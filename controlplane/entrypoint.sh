#!/bin/sh
# Entrypoint for the control-plane image. One image, three roles:
#   web        - gunicorn API/UI server (default)
#   scheduler  - enqueues due monitor checks
#   dispatcher - delivers alert notifications
# Any other argument is passed through to manage.py (e.g. `migrate`).
set -e

case "$1" in
  web)
    if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
      python manage.py migrate --noinput
      python manage.py ensure_regions
    fi
    exec gunicorn pulsegrid.wsgi:application \
      --bind 0.0.0.0:8000 \
      --workers "${GUNICORN_WORKERS:-4}" \
      --threads "${GUNICORN_THREADS:-4}" \
      --timeout "${GUNICORN_TIMEOUT:-60}" \
      --access-logfile -
    ;;
  scheduler)
    exec python manage.py runscheduler
    ;;
  dispatcher)
    exec python manage.py rundispatcher
    ;;
  *)
    exec python manage.py "$@"
    ;;
esac
