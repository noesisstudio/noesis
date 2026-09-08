FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir faster-whisper==1.2.1 fastapi==0.141.1 uvicorn==0.52.4 python-dotenv==1.2.3
COPY src/noesis/__init__.py /app/noesis/__init__.py
COPY src/noesis/config.py /app/noesis/config.py
COPY src/noesis/private_voice.py /app/noesis/private_voice.py
COPY src/noesis/adapters/__init__.py /app/noesis/adapters/__init__.py
COPY src/noesis/adapters/transcription.py /app/noesis/adapters/transcription.py
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('Systran/faster-whisper-small', revision='536b0662742c02347bc0e980a01041f333bce120', local_dir='/models/small')"
ENV NOESIS_WHISPER_MODEL=/models/small NOESIS_WHISPER_DIR=/models HF_HUB_OFFLINE=1 NOESIS_WHISPER_MAX_SECONDS=120
RUN useradd --uid 10001 --create-home voice && chown -R voice:voice /models /app
USER voice
CMD ["python", "-m", "noesis.private_voice"]
