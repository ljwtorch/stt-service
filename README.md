# stt-service 语音转文字服务

基于 [OpenAI Whisper](https://github.com/openai/whisper) 的语音转文字 HTTP API 服务，运行在 Linux Debian x86 服务器上，使用 CPU 推理。

**功能特性：**
- 内置 Web 前端页面，支持拖拽上传音频文件
- 异步任务处理，上传后立即返回，后台自动转写
- 转写结果支持 TXT / SRT 字幕 / JSON 三种格式下载
- SQLite 持久化任务记录，服务重启数据不丢失
- 同时提供同步和异步两套 API 接口

## 系统要求

- **操作系统**: Linux Debian (x86_64)
- **Python**: 3.12
- **系统依赖**: ffmpeg

## 安装

### 1. 安装系统依赖

```bash
sudo apt update
sudo apt install -y ffmpeg python3.12 python3.12-venv
```

### 2. 克隆项目并创建虚拟环境

```bash
git clone <你的仓库地址> whisper
cd whisper
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. 安装 Python 依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> 首次启动时 Whisper 会自动下载模型文件（medium 约 1.5 GB），需要耐心等待。

## 配置

所有配置均支持通过**环境变量**或项目根目录下的 `.env` 文件覆盖。

| 环境变量 | 说明 | 默认值 |
|---|---|---|
| `WHISPER_MODEL` | Whisper 模型名称（tiny / base / small / medium / large） | `medium` |
| `WHISPER_LANGUAGE` | 默认转写语言代码 | `zh` |
| `UPLOAD_MAX_SIZE_MB` | 上传文件最大 MB | `25` |
| `HOST` | 服务监听地址 | `0.0.0.0` |
| `PORT` | 服务监听端口 | `30000` |
| `DATA_DIR` | 数据目录（存放数据库和转写结果文件） | `./data` |
| `MAX_WORKERS` | 后台转写线程数（CPU 推理建议为 1） | `1` |

`.env` 文件示例：

```
WHISPER_MODEL=medium
WHISPER_LANGUAGE=zh
PORT=30000
DATA_DIR=./data
```

## 启动服务

### 直接运行

```bash
source .venv/bin/activate
python app.py
```

或使用 uvicorn 命令：

```bash
uvicorn app:app --host 0.0.0.0 --port 30000
```

服务启动后会自动：
1. 检测并初始化 SQLite 数据库（位于 `DATA_DIR/whisper.db`）
2. 加载 Whisper 模型（medium 约需 1-2 分钟）
3. 启动后台任务管理器

加载完成后输出日志提示服务已就绪。

### 访问前端页面

服务启动后，浏览器访问 **http://<服务器IP>:30000** 即可使用 Web 前端页面。

页面功能：
- 拖拽或点击上传音频文件
- 选择转写语言
- 实时查看任务列表和转写状态
- 查看转写结果详情（完整文本 + 分段时间轴）
- 下载 TXT / SRT / JSON 格式结果文件

### Docker 运行

```bash
# 构建镜像
docker build -t whisper-service .

# 运行容器（挂载模型缓存和数据目录）
docker run -d \
  --name whisper \
  -p 30000:30000 \
  -v whisper-models:/root/.cache/whisper \
  -v whisper-data:/app/data \
  whisper-service
```

## API 文档

启动服务后访问交互式 API 文档：

- **Swagger UI**: http://<服务器IP>:30000/docs
- **ReDoc**: http://<服务器IP>:30000/redoc

### GET /api/v1/health

健康检查，返回服务状态和当前加载的模型名称。

**响应示例**：

```json
{
  "status": "ok",
  "model": "medium"
}
```

### POST /api/v1/transcribe（同步接口）

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

### POST /api/v1/tasks（异步接口）

上传音频文件并提交后台异步转写任务，立即返回 `task_id`。

**请求参数**：同上

**响应示例**：

```json
{
  "task_id": "a1b2c3d4e5f6...",
  "status": "pending"
}
```

### GET /api/v1/tasks

获取所有任务列表，按创建时间倒序。

**查询参数**：

| 参数 | 类型 | 说明 |
|---|---|---|
| `limit` | int | 最大返回数量（默认 100） |
| `offset` | int | 偏移量（默认 0） |

### GET /api/v1/tasks/{task_id}

获取单个任务的详细信息和当前状态。

**任务状态说明**：

| 状态 | 说明 |
|---|---|
| `pending` | 已提交，等待处理 |
| `processing` | 正在转写中 |
| `completed` | 转写完成，可下载结果 |
| `failed` | 转写失败 |

### DELETE /api/v1/tasks/{task_id}

删除任务记录及其结果文件。

### GET /api/v1/tasks/{task_id}/download/{format}

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

## 项目结构

```
whisper/
├── .gitignore          # Git 忽略规则
├── README.md           # 项目文档
├── requirements.txt    # Python 依赖
├── config.py           # 配置管理（环境变量）
├── schemas.py          # Pydantic 请求/响应模型
├── service.py          # Whisper 转写服务（单例模式）
├── database.py         # SQLite 数据库管理（自动初始化）
├── task_manager.py     # 异步任务管理器（线程池）
├── app.py              # FastAPI 应用主入口
├── Dockerfile          # Docker 构建文件
├── static/
│   └── index.html      # 前端单页面
└── data/               # 运行时数据（自动创建）
    ├── whisper.db       # SQLite 数据库
    └── results/         # 转写结果文件
        └── {task_id}/
            ├── result.txt
            ├── result.srt
            └── result.json
```

## 常见问题

**Q: 模型下载太慢怎么办？**

可以配置国内镜像或手动下载模型文件放到 `~/.cache/whisper/` 目录下：

```bash
mkdir -p ~/.cache/whisper
# 从 https://openaipublic.azureedge.net/main/whisper/models/<模型名>.pt 手动下载
# 例如 medium 模型：
# wget -P ~/.cache/whisper/ https://openaipublic.azureedge.net/main/whisper/models/d7440d3dcad73647b49a29cc32b82f3c.model
```

**Q: CPU 转写速度慢怎么办？**

可以尝试换用更小的模型（如 `small`），或考虑使用 `faster-whisper` 替代方案以获得更好的 CPU 推理性能。

**Q: 如何后台运行服务？**

使用 `systemd` 创建服务，或使用 `tmux`/`screen`，或通过 Docker 以 daemon 模式运行（见 Docker 运行章节）。
