# Python app image: Vosk STT + UDP capture + trigger loop.
# No local mic needed — audio arrives over UDP from a microphone source.
FROM python:3.13-slim

WORKDIR /app

# Copy the project source.
COPY . /app/

# Install deps.
RUN pip install --no-cache-dir -r requirements.txt

# Vosk model is downloaded on first run into /app/models (volume-mounted).
# To pre-bake it, uncomment the next line (needs network at build time):
# RUN python -c "from stt import VoskSTT; VoskSTT().download_model()"

EXPOSE 5000/udp
CMD ["python", "loop.py", "--udp"]
