"""
日志配置模块，基于 loguru 提供统一的日志管理。

功能：
- 启动阶段：日志同时输出到 stdout 和文件
- 运行阶段：stdout 仅保留启动日志，后续日志仅写入文件
- 文件按大小自动轮转并 gzip 压缩归档
- 文件名包含年月日时分时间戳后缀
"""

import logging
import sys
from pathlib import Path

from loguru import logger

from config import settings


class InterceptHandler(logging.Handler):
    """
    将标准库 logging 的日志重定向到 loguru。

    确保 openai-whisper 等第三方库的日志也能被统一管理和写入文件。
    """

    def emit(self, record: logging.LogRecord) -> None:
        # 获取对应 loguru 级别
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 从调用栈找到真正产生日志的位置
        frame = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging() -> int:
    """
    初始化日志系统。

    - 移除 loguru 默认 handler
    - 添加 stdout handler（启动阶段可见）
    - 添加文件 handler（按大小轮转、gzip 压缩、带时间戳文件名）
    - 拦截标准库 logging 至 loguru

    Returns:
        console_handler_id: 用于后续移除 stdout handler
    """
    # 移除 loguru 默认 handler
    logger.remove()

    # 创建日志目录
    settings.LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 添加 stdout handler（启动阶段使用，INFO 级别）
    console_handler_id = logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
               "<level>{level: <8}</level> | "
               "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
               "<level>{message}</level>",
        colorize=True,
    )

    # 添加文件 handler（带时间戳文件名，按大小轮转，gzip 压缩）
    log_file = settings.LOG_DIR / "stt-service_{time:YYYYMMDD_HHmm}.log"
    logger.add(
        str(log_file),
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation=f"{settings.LOG_MAX_SIZE_MB} MB",
        compression="gz",
        retention=f"{settings.LOG_RETENTION_DAYS} days",
        encoding="utf-8",
    )

    # 拦截标准库 logging，统一到 loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    # 降低 uvicorn 标准 logging 的日志级别，避免重复输出
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(name).handlers = [InterceptHandler()]
        logging.getLogger(name).propagate = False

    logger.info("日志系统已初始化，日志目录: {}", settings.LOG_DIR)

    return console_handler_id


def disable_console_logging(handler_id: int) -> None:
    """
    移除 stdout handler，此后日志仅写入文件。

    应在应用完成启动、所有组件就绪后调用。
    """
    logger.remove(handler_id)
    logger.info("已切换到文件日志模式，stdout 不再输出日志")
