import logging
import threading
from pathlib import Path
from typing import Optional

import whisper

logger = logging.getLogger(__name__)


class WhisperService:
    """Whisper 转写服务，单例模式，启动时加载模型到 CPU"""

    _instance: Optional["WhisperService"] = None
    _lock = threading.Lock()

    def __init__(self, model_name: str = "medium"):
        self.model_name = model_name
        self._model: Optional[whisper.Whisper] = None
        self._model_lock = threading.Lock()

    @classmethod
    def get_instance(cls, model_name: str = "medium") -> "WhisperService":
        """获取或创建单例实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(model_name=model_name)
        return cls._instance

    def load_model(self) -> None:
        """加载 Whisper 模型到 CPU，仅在首次调用时执行"""
        if self._model is not None:
            return

        with self._model_lock:
            if self._model is not None:
                return

            logger.info("正在加载 Whisper 模型: %s (CPU 模式)...", self.model_name)
            self._model = whisper.load_model(self.model_name, device="cpu")
            logger.info("模型加载完成: %s", self.model_name)

    def transcribe(
        self,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> dict:
        """
        对音频文件进行转写。

        Args:
            audio_path: 音频文件路径
            language: 语言代码（如 'zh'、'en'），为 None 时使用默认语言

        Returns:
            包含 text、language、segments 的字典
        """
        if self._model is None:
            raise RuntimeError("模型尚未加载，请先调用 load_model()")

        options = {}
        if language:
            options["language"] = language

        # whisper CPU 转写非线程安全，加锁保护
        with self._model_lock:
            result = self._model.transcribe(str(audio_path), **options)

        segments = [
            {
                "id": seg["id"],
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
            }
            for seg in result.get("segments", [])
        ]

        return {
            "text": result.get("text", "").strip(),
            "language": result.get("language", language or "unknown"),
            "segments": segments,
        }
