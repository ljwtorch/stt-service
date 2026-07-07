from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，支持通过环境变量覆盖"""

    # Whisper 模型名称：tiny, base, small, medium, large
    WHISPER_MODEL: str = "medium"

    # 默认转写语言，设为 None 则自动检测
    WHISPER_LANGUAGE: str = "zh"

    # 上传文件最大 MB
    UPLOAD_MAX_SIZE_MB: int = 25

    # 服务监听地址
    HOST: str = "0.0.0.0"

    # 服务监听端口
    PORT: int = 30000

    # 数据根目录（存放 SQLite 数据库和转写结果文件）
    DATA_DIR: Path = Path("./data")

    # 后台转写线程数（CPU 推理建议设为 1，串行处理即可）
    MAX_WORKERS: int = 1

    # 日志目录
    LOG_DIR: Path = Path("./data/logs")

    # 单个日志文件最大大小（MB），超过后自动轮转压缩
    LOG_MAX_SIZE_MB: int = 10

    # 日志文件保留天数
    LOG_RETENTION_DAYS: int = 30

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()
