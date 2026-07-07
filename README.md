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
git clone <你的仓库地址> stt-service
cd stt-service
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
| `LOG_DIR` | 日志文件目录 | `./data/logs` |
| `LOG_MAX_SIZE_MB` | 单个日志文件最大大小（MB），超过后自动轮转压缩 | `10` |
| `LOG_RETENTION_DAYS` | 日志文件保留天数 | `30` |

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
1. 检测并初始化 SQLite 数据库（位于 `DATA_DIR/stt-service.db`）
2. 加载 Whisper 模型（medium 约需 1-2 分钟）
3. 启动后台任务管理器

加载完成后输出日志提示服务已就绪。

### Docker 运行

```bash
# 拉取镜像
docker pull ghcr.io/ljwtorch/stt-service:latest

# 运行容器（挂载模型缓存、数据目录和日志目录）
docker run -d \
  --name stt-service \
  -p 30000:30000 \
  -v stt-service-models:/root/.cache/whisper \
  -v stt-service-data:/app/data \
  -v stt-service-logs:/app/data/logs \
  ghcr.io/ljwtorch/stt-service:latest
```

## API 文档

详细的 API 接口文档请参阅 [docs/api.md](docs/api.md)。

## 使用示例

curl 调用示例及响应示例请参阅 [docs/api.md](docs/api.md#使用示例)。

## 项目结构

```
stt-service/
├── .gitignore          # Git 忽略规则
├── README.md           # 项目文档
├── requirements.txt    # Python 依赖
├── config.py           # 配置管理（环境变量）
├── schemas.py          # Pydantic 请求/响应模型
├── logging_config.py   # 日志配置（loguru 统一管理）
├── service.py          # Whisper 转写服务（单例模式）
├── database.py         # SQLite 数据库管理（自动初始化）
├── task_manager.py     # 异步任务管理器（线程池）
├── app.py              # FastAPI 应用主入口
├── Dockerfile          # Docker 构建文件
├── static/
│   └── index.html      # 前端单页面
└── data/               # 运行时数据（自动创建）
    ├── stt-service.db       # SQLite 数据库
    ├── logs/            # 日志文件（自动轮转压缩）
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
