# API Documentation

After starting the service, access interactive API docs at:

- **Swagger UI**: http://\<server-ip\>:30000/docs
- **ReDoc**: http://\<server-ip\>:30000/redoc

## GET /api/v1/health

Health check endpoint that returns the service status and currently loaded model.

**Response example**:

```json
{
  "status": "ok",
  "model": "medium"
}
```

## POST /api/v1/transcribe (Synchronous)

Upload an audio file and wait for the transcription result. Suitable for small files.

**Request parameters**:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `file` | UploadFile | Yes | Audio file (wav/mp3/flac/m4a/ogg/webm/mp4) |
| `language` | string | No | Language code (e.g. `zh`, `en`); defaults to config value |

**Response fields**:

| Field | Type | Description |
|---|---|---|
| `text` | string | Full transcription text |
| `language` | string | Detected or specified language |
| `segments` | array | List of segment results |
| `segments[].id` | int | Segment ID |
| `segments[].start` | float | Start time (seconds) |
| `segments[].end` | float | End time (seconds) |
| `segments[].text` | string | Segment text |

## POST /api/v1/tasks (Asynchronous)

Upload an audio file and submit it for background transcription. Returns a `task_id` immediately.

**Request parameters**: Same as above

**Response example**:

```json
{
  "task_id": "a1b2c3d4e5f6...",
  "status": "pending"
}
```

## GET /api/v1/tasks

List all tasks ordered by creation time (descending).

**Query parameters**:

| Parameter | Type | Description |
|---|---|---|
| `limit` | int | Max results (default 100) |
| `offset` | int | Offset (default 0) |

## GET /api/v1/tasks/{task_id}

Get details and current status of a single task.

**Task statuses**:

| Status | Description |
|---|---|
| `pending` | Submitted, waiting to be processed |
| `processing` | Transcription in progress |
| `completed` | Transcription finished, results available for download |
| `failed` | Transcription failed |

## DELETE /api/v1/tasks/{task_id}

Delete a task record and its result files.

## GET /api/v1/tasks/{task_id}/download/{format}

Download the transcription result file.

**Supported formats**:

| format | Description |
|---|---|
| `txt` | Plain text with the full transcription |
| `srt` | SRT subtitle file with timestamps, importable into media players |
| `json` | Structured JSON with full text and segment data |

## Usage Examples

### curl

```bash
# Synchronous transcription (waits for completion)
curl -X POST http://<server-ip>:30000/api/v1/transcribe \
  -F "file=@audio.mp3"

# Submit async task (returns task_id immediately)
curl -X POST http://<server-ip>:30000/api/v1/tasks \
  -F "file=@audio.mp3"

# List all tasks
curl http://<server-ip>:30000/api/v1/tasks

# Get task details
curl http://<server-ip>:30000/api/v1/tasks/<task_id>

# Download SRT subtitle file
curl -O http://<server-ip>:30000/api/v1/tasks/<task_id>/download/srt

# Delete a task
curl -X DELETE http://<server-ip>:30000/api/v1/tasks/<task_id>

# Health check
curl http://<server-ip>:30000/api/v1/health
```

**Response example**:

```json
{
  "text": "Hello, welcome to the speech-to-text service.",
  "language": "en",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 3.5,
      "text": "Hello, welcome to the speech-to-text service."
    }
  ]
}
```
