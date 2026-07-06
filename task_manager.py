"""
异步任务管理器，负责在后台线程池中执行 Whisper 转写任务。

任务提交后立即返回，转写完成后将结果保存到数据库和文件系统。
"""

import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import database as db
from config import settings
from service import WhisperService

logger = logging.getLogger(__name__)


def _get_results_dir(task_id: str) -> Path:
    """返回任务结果文件目录：DATA_DIR/results/{task_id}/"""
    return settings.DATA_DIR / "results" / task_id


def format_srt(segments: list[dict]) -> str:
    """
    将 segments 转换为 SRT 字幕格式。

    示例输出：
    1
    00:00:00,000 --> 00:00:03,500
    你好，欢迎使用语音转文字服务。

    2
    00:00:04,000 --> 00:00:08,200
    这是一段示例文字。
    """
    lines = []
    for i, seg in enumerate(segments, start=1):
        start = _format_srt_time(seg["start"])
        end = _format_srt_time(seg["end"])
        text = seg["text"]
        lines.append(f"{i}")
        lines.append(f"{start} --> {end}")
        lines.append(text)
        lines.append("")  # 空行分隔
    return "\n".join(lines)


def _format_srt_time(seconds: float) -> str:
    """将秒数转换为 SRT 时间格式 HH:MM:SS,mmm"""
    total_ms = int(seconds * 1000)
    hours, total_ms = divmod(total_ms, 3_600_000)
    minutes, total_ms = divmod(total_ms, 60_000)
    secs, ms = divmod(total_ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def save_results(task_id: str, text: str, segments: list[dict]) -> Path:
    """
    将转写结果保存为三种格式文件。

    文件保存至 DATA_DIR/results/{task_id}/:
    - result.txt: 纯文本
    - result.srt: SRT 字幕
    - result.json: 结构化 JSON

    Returns:
        结果文件目录路径
    """
    results_dir = _get_results_dir(task_id)
    results_dir.mkdir(parents=True, exist_ok=True)

    # 纯文本
    (results_dir / "result.txt").write_text(text, encoding="utf-8")

    # SRT 字幕
    srt_content = format_srt(segments)
    (results_dir / "result.srt").write_text(srt_content, encoding="utf-8")

    # 结构化 JSON
    result_json = {
        "text": text,
        "segments": segments,
    }
    (results_dir / "result.json").write_text(
        json.dumps(result_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    logger.info("结果文件已保存至: %s", results_dir)
    return results_dir


def delete_results(task_id: str) -> None:
    """删除任务的结果文件目录"""
    results_dir = _get_results_dir(task_id)
    if results_dir.exists():
        import shutil
        shutil.rmtree(results_dir, ignore_errors=True)
        logger.info("已删除结果文件: %s", results_dir)


def get_result_file(task_id: str, fmt: str) -> Optional[Path]:
    """
    获取指定格式的结果文件路径。

    Args:
        task_id: 任务 ID
        fmt: 文件格式（txt/srt/json）

    Returns:
        文件路径，不存在时返回 None
    """
    results_dir = _get_results_dir(task_id)
    file_path = results_dir / f"result.{fmt}"
    return file_path if file_path.exists() else None


class TaskManager:
    """后台任务管理器，使用线程池执行转写任务"""

    def __init__(self, max_workers: int = 1):
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="whisper-worker")
        self._service = WhisperService.get_instance()
        logger.info("TaskManager 已初始化，最大工作线程数: %d", max_workers)

    def submit_task(
        self,
        task_id: str,
        audio_path: Path,
        language: Optional[str] = None,
    ) -> None:
        """
        提交后台转写任务。

        任务立即在线程池中排队执行，不阻塞调用方。
        """
        self._executor.submit(self._run_task, task_id, audio_path, language)
        logger.info("任务已提交至后台: %s", task_id)

    def _run_task(
        self,
        task_id: str,
        audio_path: Path,
        language: Optional[str],
    ) -> None:
        """在线程中执行转写任务（内部方法）"""
        try:
            # 更新状态为 processing
            db.update_task_processing(task_id)
            logger.info("开始转写任务: %s", task_id)

            # 执行转写
            lang = language or settings.WHISPER_LANGUAGE
            result = self._service.transcribe(audio_path, language=lang)

            text = result["text"]
            segments = result["segments"]
            detected_lang = result["language"]

            # 保存结果到数据库
            db.update_task_completed(task_id, text, segments, detected_lang)

            # 保存结果文件
            save_results(task_id, text, segments)

            logger.info("转写任务完成: %s，语言: %s，文本长度: %d", task_id, detected_lang, len(text))

        except Exception as e:
            logger.exception("转写任务失败: %s", task_id)
            db.update_task_failed(task_id, str(e))

        finally:
            # 清理临时音频文件
            if audio_path.exists():
                try:
                    os.remove(audio_path)
                    logger.info("已清理临时音频文件: %s", audio_path)
                except OSError as e:
                    logger.warning("清理临时文件失败 %s: %s", audio_path, e)

    def shutdown(self) -> None:
        """优雅关闭线程池，等待所有任务完成"""
        logger.info("正在关闭 TaskManager...")
        self._executor.shutdown(wait=True)
        logger.info("TaskManager 已关闭")
