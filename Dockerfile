FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    xauth \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY brow/ /app/brow/
RUN pip install --no-cache-dir /app/brow/

RUN playwright install --with-deps chromium

COPY benchmarks/ /app/benchmarks/
RUN pip install --no-cache-dir -r /app/benchmarks/requirements.txt

COPY skills/ /app/skills/

ENV DISPLAY=:99

ENTRYPOINT ["sh", "-c", "Xvfb :99 -screen 0 1280x720x24 -nolisten tcp & sleep 1 && exec \"$@\"", "--"]
CMD ["python", "-m", "benchmarks", "--help"]
