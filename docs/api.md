# API 文档

启动服务后访问交互式 API 文档：

- **Swagger UI**: http://\<服务器IP\>:30000/docs
- **ReDoc**: http://\<服务器IP\>:30000/redoc

## GET /api/v1/health

健康检查，返回服务状态和当前加载的模型名称。

**响应示例**：

```json
{
  "status": "ok",
  "model": "medium"
}
```

## POST /api/v1/transcribe（同步接口）

上传音频文件并同步等待转写结果，适用于小文件场景。

**请求参数**：

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `file` | UploadFile | 是 | 音频文件，支持 wav/mp3/flac/m4a/ogg/webm/mp4 |
| `language` | string | 否 | 语言代码（如 `zh`、`en`），不填使用配置默认值 |

**响应字段**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `text` | string | 完整转写文本 |
| `language` | string | 检测到/指定的语言 |
| `segments` | array | 分段结果列表 |
| `segments[].id` | int | 分段 ID |
| `segments[].start` | float | 开始时间（秒） |
| `segments[].end` | float | 结束时间（秒） |
| `segments[].text` | string | 分段文本 |

## POST /api/v1/tasks（异步接口）

上传音频文件并提交后台异步转写任务，立即返回 `task_id`。

**请求参数**：同上

**响应示例**：

```json
{
  "task_id": "a1b2c3d4e5f6...",
  "status": "pending"
}
```

## GET /api/v1/tasks

获取所有任务列表，按创建时间倒序。

**查询参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `limit` | int | 最大返回数量（默认 100） |
| `offset` | int | 偏移量（默认 0） |

## GET /api/v1/tasks/{task_id}

获取单个任务的详细信息和当前状态。

**任务状态说明**：

| 状态 | 说明 |
|---|---|
| `pending` | 已提交，等待处理 |
| `processing` | 正在转写中 |
| `completed` | 转写完成，可下载结果 |
| `failed` | 转写失败 |

## DELETE /api/v1/tasks/{task_id}

删除任务记录及其结果文件。

## GET /api/v1/tasks/{task_id}/download/{format}

下载转写结果文件。

**支持的格式**：

| format | 说明 |
|---|---|
| `txt` | 纯文本，包含完整转写内容 |
| `srt` | SRT 字幕文件，含时间轴，可直接导入播放器 |
| `json` | 结构化 JSON，包含完整文本和分段信息 |

## 使用示例

### curl 调用

```bash
# 同步转写（等待完成后返回结果）
curl -X POST http://<服务器IP>:30000/api/v1/transcribe \
  -F "file=@audio.mp3"

# 提交异步转写任务（立即返回 task_id）
curl -X POST http://<服务器IP>:30000/api/v1/tasks \
  -F "file=@audio.mp3"

# 查看任务列表
curl http://<服务器IP>:30000/api/v1/tasks

# 查看单个任务详情
curl http://<服务器IP>:30000/api/v1/tasks/<task_id>

# 下载 SRT 字幕文件
curl -O http://<服务器IP>:30000/api/v1/tasks/<task_id>/download/srt

# 删除任务
curl -X DELETE http://<服务器IP>:30000/api/v1/tasks/<task_id>

# 健康检查
curl http://<服务器IP>:30000/api/v1/health
```

**响应示例**：

```json
{
  "text": "你好，欢迎使用语音转文字服务。",
  "language": "zh",
  "segments": [
    {
      "id": 0,
      "start": 0.0,
      "end": 3.5,
      "text": "你好，欢迎使用语音转文字服务。"
    }
  ]
}
```
