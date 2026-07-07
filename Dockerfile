FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Whisper 模型缓存、数据目录、日志目录，可通过 volume 挂载持久化
VOLUME ["/root/.cache/whisper", "/app/data", "/app/data/logs"]

EXPOSE 30000

CMD ["python", "app.py"]
