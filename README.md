# stt-service

[中文文档](README.zh.md)

A speech-to-text HTTP API service based on [OpenAI Whisper](https://github.com/openai/whisper), designed for CPU inference on Linux Debian x86 servers.

**Features:**
- Built-in web UI with drag-and-drop audio file upload
- Asynchronous task processing: upload and get an immediate response, transcription runs in the background
- Download results in TXT, SRT (subtitle), and JSON formats
- SQLite-backed persistent task records survive service restarts
- Both synchronous and asynchronous API endpoints

## System Requirements

- **OS**: Linux Debian (x86_64)
- **Python**: 3.12
- **System dependency**: ffmpeg

## Installation

### 1. Install system dependencies

```bash
sudo apt update
sudo apt install -y ffmpeg python3.12 python3.12-venv
```

### 2. Clone and create virtual environment

```bash
git clone <your-repo-url> stt-service
cd stt-service
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> On first startup, Whisper will automatically download the model file (medium ~1.5 GB). This may take a while.

## Configuration

All settings can be overridden via **environment variables** or a `.env` file in the project root.

| Variable | Description | Default |
|---|---|---|
| `WHISPER_MODEL` | Whisper model name (tiny / base / small / medium / large) | `medium` |
| `WHISPER_LANGUAGE` | Default transcription language code | `zh` |
| `UPLOAD_MAX_SIZE_MB` | Maximum upload file size in MB | `25` |
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server listen port | `30000` |
| `DATA_DIR` | Data directory (database and transcription results) | `./data` |
| `MAX_WORKERS` | Background transcription threads (1 recommended for CPU) | `1` |
| `LOG_DIR` | Log file directory | `./data/logs` |
| `LOG_MAX_SIZE_MB` | Max size per log file before rotation | `10` |
| `LOG_RETENTION_DAYS` | Log retention days | `30` |

Example `.env` file:

```
WHISPER_MODEL=medium
WHISPER_LANGUAGE=zh
PORT=30000
DATA_DIR=./data
```

## Running the Service

### Directly

```bash
source .venv/bin/activate
python app.py
```

Or with uvicorn:

```bash
uvicorn app:app --host 0.0.0.0 --port 30000
```

On startup, the service will:
1. Initialize the SQLite database (at `DATA_DIR/stt-service.db`)
2. Load the Whisper model (medium takes about 1-2 minutes)
3. Start the background task manager

A log message will confirm when the service is ready.

### Docker

```bash
# Pull the image
docker pull ghcr.io/ljwtorch/stt-service:latest

# Run the container (mount model cache, data, and logs)
docker run -d \
  --name stt-service \
  -p 30000:30000 \
  -v stt-service-models:/root/.cache/whisper \
  -v stt-service-data:/app/data \
  -v stt-service-logs:/app/data/logs \
  ghcr.io/ljwtorch/stt-service:latest
```

## API Documentation

See [docs/api.md](docs/api.md) for detailed API reference.

## Usage Examples

See [docs/api.md](docs/api.md#usage-examples) for curl examples and sample responses.

## Project Structure

```
stt-service/
├── .gitignore          # Git ignore rules
├── README.md           # Project documentation (English)
├── README.zh.md        # Project documentation (Chinese)
├── requirements.txt    # Python dependencies
├── config.py           # Configuration management (env vars)
├── schemas.py          # Pydantic request/response models
├── logging_config.py   # Logging configuration (loguru)
├── service.py          # Whisper transcription service (singleton)
├── database.py         # SQLite database management (auto-init)
├── task_manager.py     # Async task manager (thread pool)
├── app.py              # FastAPI application entry point
├── Dockerfile          # Docker build file
├── static/
│   ├── icon.svg        # App icon
│   └── index.html      # Single-page frontend
├── docs/
│   ├── api.md          # API docs (English)
│   └── api.zh.md       # API docs (Chinese)
└── data/               # Runtime data (auto-created)
    ├── stt-service.db       # SQLite database
    ├── logs/            # Log files (auto-rotated)
    └── results/         # Transcription result files
        └── {task_id}/
            ├── result.txt
            ├── result.srt
            └── result.json
```

## FAQ

**Q: Model download is too slow.**

You can configure a mirror or manually download the model to `~/.cache/whisper/`:

```bash
mkdir -p ~/.cache/whisper
# Download from https://openaipublic.azureedge.net/main/whisper/models/<model-name>.pt
# Example for medium:
# wget -P ~/.cache/whisper/ https://openaipublic.azureedge.net/main/whisper/models/d7440d3dcad73647b49a29cc32b82f3c.model
```

**Q: CPU transcription is slow.**

Try a smaller model (e.g. `small`), or consider using `faster-whisper` for better CPU inference performance.

**Q: How do I run the service in the background?**

Use `systemd`, `tmux`/`screen`, or Docker in daemon mode (see the Docker section).
