import os
import tempfile
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

import uvicorn

import database as db
from config import settings
from logging_config import disable_console_logging, setup_logging
from schemas import (
    HealthResponse,
    Segment,
    TaskListResponse,
    TaskStatus,
    TaskSubmitResponse,
    TranscribeResponse,
)
from service import WhisperService
from task_manager import TaskManager, delete_results, get_result_file

# 允许的音频文件扩展名
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".webm", ".mp4"}

# 允许的下载格式
ALLOWED_FORMATS = {"txt", "srt", "json"}

# MIME 类型映射
FORMAT_MIME_TYPES = {
    "txt": "text/plain; charset=utf-8",
    "srt": "text/plain; charset=utf-8",
    "json": "application/json; charset=utf-8",
}

# 临时上传目录
UPLOAD_DIR = Path(tempfile.gettempdir()) / "whisper_uploads"

# 静态文件目录
STATIC_DIR = Path(__file__).parent / "static"

# 全局 TaskManager 实例
_task_manager: Optional[TaskManager] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化所有组件，退出时清理"""
    global _task_manager

    # 初始化日志系统（stdout + 文件双输出）
    console_handler_id = setup_logging()

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # 初始化数据库（自动检测并建表）
    db.init_db()

    # 初始化 Whisper 模型
    logger.info("正在初始化 Whisper 服务，模型: {} ...", settings.WHISPER_MODEL)
    service = WhisperService.get_instance(model_name=settings.WHISPER_MODEL)
    service.load_model()
    logger.info("Whisper 模型加载完成")

    # 初始化 TaskManager
    _task_manager = TaskManager(max_workers=settings.MAX_WORKERS)

    logger.info("所有组件已就绪，监听 {}:{}", settings.HOST, settings.PORT)

    # 启动完成，关闭 stdout 日志，后续日志仅写入文件
    disable_console_logging(console_handler_id)

    yield

    # 关闭
    if _task_manager:
        _task_manager.shutdown()
    logger.info("服务已关闭")


app = FastAPI(
    title="Whisper 语音转文字服务",
    description="基于 OpenAI Whisper 的语音转文字 HTTP API，支持 CPU 推理和异步任务",
    version="2.0.0",
    lifespan=lifespan,
)

# 挂载静态文件目录
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _validate_file(file: UploadFile) -> None:
    """校验上传文件的类型"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，支持的格式: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )


async def _save_upload(file: UploadFile) -> Path:
    """
    读取并保存上传文件到临时目录，返回临时文件路径。
    同时校验文件大小。
    """
    ext = Path(file.filename).suffix.lower()
    temp_filename = f"{uuid.uuid4().hex}{ext}"
    temp_path = UPLOAD_DIR / temp_filename

    content = await file.read()
    max_bytes = settings.UPLOAD_MAX_SIZE_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大，最大允许 {settings.UPLOAD_MAX_SIZE_MB} MB",
        )

    with open(temp_path, "wb") as f:
        f.write(content)

    return temp_path


# ============================================================
# 前端页面
# ============================================================


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index():
    """返回前端单页面"""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="前端页面不存在")
    return HTMLResponse(content=index_path.read_text(encoding="utf-8"))


# ============================================================
# 健康检查
# ============================================================


@app.get("/api/v1/health", response_model=HealthResponse, summary="健康检查")
async def health_check():
    """返回服务健康状态和当前加载的模型名称"""
    return HealthResponse(status="ok", model=settings.WHISPER_MODEL)


# ============================================================
# 同步转写接口（向后兼容）
# ============================================================


@app.post(
    "/api/v1/transcribe",
    response_model=TranscribeResponse,
    summary="音频转写（同步）",
    description="上传音频文件并同步等待转写结果，适用于小文件和低延迟场景",
)
async def transcribe_audio(
    file: UploadFile = File(..., description="音频文件（wav/mp3/flac/m4a/ogg/webm/mp4）"),
    language: Optional[str] = Query(
        default=None,
        description="转写语言代码，如 'zh'、'en'。不填则使用配置默认值",
    ),
):
    """接收音频文件，同步等待转写完成并返回结构化结果。"""
    _validate_file(file)

    temp_path = await _save_upload(file)

    try:
        logger.info("收到同步转写请求: {} ({:.2f} MB)", file.filename, temp_path.stat().st_size / 1024 / 1024)

        service = WhisperService.get_instance()
        lang = language or settings.WHISPER_LANGUAGE
        result = service.transcribe(temp_path, language=lang)

        logger.info("同步转写完成: {}，语言: {}", file.filename, result["language"])

        return TranscribeResponse(
            text=result["text"],
            language=result["language"],
            segments=[Segment(**seg) for seg in result["segments"]],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("同步转写失败: {}", e)
        raise HTTPException(status_code=500, detail=f"转写失败: {str(e)}") from e
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except OSError as e:
                logger.warning("清理临时文件失败 {}: {}", temp_path, e)


# ============================================================
# 异步任务接口
# ============================================================


@app.post(
    "/api/v1/tasks",
    response_model=TaskSubmitResponse,
    summary="提交异步转写任务",
    description="上传音频文件并提交后台异步转写任务，立即返回 task_id",
)
async def submit_task(
    file: UploadFile = File(..., description="音频文件（wav/mp3/flac/m4a/ogg/webm/mp4）"),
    language: Optional[str] = Query(
        default=None,
        description="转写语言代码，如 'zh'、'en'。不填则使用配置默认值",
    ),
):
    """上传音频文件并提交后台转写任务。"""
    _validate_file(file)

    task_id = uuid.uuid4().hex
    temp_path = await _save_upload(file)

    logger.info("提交异步任务: {} -> task_id={}", file.filename, task_id)

    # 在数据库中创建任务记录
    lang = language or settings.WHISPER_LANGUAGE
    db.create_task(task_id, file.filename, lang)

    # 提交至后台线程池
    _task_manager.submit_task(task_id, temp_path, lang)

    return TaskSubmitResponse(task_id=task_id, status="pending")


@app.get(
    "/api/v1/tasks",
    response_model=TaskListResponse,
    summary="获取任务列表",
    description="获取所有转写任务列表，按创建时间倒序",
)
async def list_tasks(
    limit: int = Query(default=100, ge=1, le=500, description="最大返回数量"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
):
    """获取任务列表"""
    tasks = db.list_tasks(limit=limit, offset=offset)
    return TaskListResponse(tasks=[TaskStatus(**t) for t in tasks])


@app.get(
    "/api/v1/tasks/{task_id}",
    response_model=TaskStatus,
    summary="获取任务详情",
    description="获取单个转写任务的详细信息和当前状态",
)
async def get_task(task_id: str):
    """获取单个任务详情"""
    task = db.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return TaskStatus(**task)


@app.delete(
    "/api/v1/tasks/{task_id}",
    summary="删除任务",
    description="删除任务记录及其结果文件",
)
async def delete_task(task_id: str):
    """删除任务及其结果文件"""
    task = db.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task["status"] == "processing":
        raise HTTPException(status_code=409, detail="任务正在处理中，无法删除")

    # 删除数据库记录
    db.delete_task(task_id)
    # 删除结果文件
    delete_results(task_id)

    logger.info("已删除任务: {}", task_id)
    return {"detail": "任务已删除"}


@app.get(
    "/api/v1/tasks/{task_id}/download/{fmt}",
    summary="下载结果文件",
    description="下载指定格式的转写结果文件（txt/srt/json）",
)
async def download_result(task_id: str, fmt: str):
    """下载转写结果文件"""
    if fmt not in ALLOWED_FORMATS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的格式: {fmt}，支持的格式: {', '.join(sorted(ALLOWED_FORMATS))}",
        )

    # 检查任务是否存在且已完成
    task = db.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="任务尚未完成转写")

    file_path = get_result_file(task_id, fmt)
    if file_path is None:
        raise HTTPException(status_code=404, detail="结果文件不存在")

    # 使用原始文件名作为下载文件名
    original_name = Path(task["original_filename"]).stem
    download_name = f"{original_name}.{fmt}"

    return FileResponse(
        path=str(file_path),
        filename=download_name,
        media_type=FORMAT_MIME_TYPES.get(fmt, "application/octet-stream"),
    )


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        log_config=None,  # 禁用 uvicorn 默认日志配置，由 loguru 统一管理
    )
