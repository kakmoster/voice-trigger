# Dockerfile for the always-listening HA voice trigger.
# Audio arrives over UDP from an ESPHome device (no local mic needed).
FROM python:3.13-slim

# Vosk loads the model from /app/models at runtime. The model is downloaded
# on first start if absent; to bake it in, uncomment the download step below.
WORKDIR /app

COPY requirements.txt .
# Install Python deps (no GPU / heavy ML frameworks needed for Vosk).
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# UDP port for incoming ESPHome audio stream.
EXPOSE 5000/udp

# The Vosk model is fetched automatically on first run (needs network once).
# Uncomment to pre-bake the Swedish small model into the image instead:
# RUN .venv/bin/python -c "from stt import VoskSTT; VoskSTT().download_model()"

CMD ["python", "loop.py", "--udp"]
