FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# traceroute's default UDP mode works unprivileged, so the pulsegrid user
# can run path checks without CAP_NET_RAW.
RUN apt-get update && apt-get install -y --no-install-recommends traceroute \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pulsegrid_worker ./pulsegrid_worker

RUN useradd --create-home --uid 1000 pulsegrid
USER pulsegrid

CMD ["python", "-m", "pulsegrid_worker"]
