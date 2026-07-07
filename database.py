"""
SQLite 数据库模块，负责任务持久化。

服务启动时自动检测数据库文件是否存在：
- 不存在：创建目录并初始化表结构
- 已存在：验证表结构完整性，直接使用
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

from config import settings

# 数据库文件名
DB_FILENAME = "whisper.db"

# 建表 SQL
CREATE_TASKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    language TEXT,
    text TEXT,
    segments_json TEXT,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
)
"""


def get_db_path() -> Path:
    """返回数据库文件的完整路径"""
    return settings.DATA_DIR / DB_FILENAME


def _ensure_data_dir() -> None:
    """确保数据目录存在"""
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_connection() -> sqlite3.Connection:
    """
    获取 SQLite 连接。
    自动确保数据目录存在；设置 row_factory 使查询结果为字典形式。
    """
    _ensure_data_dir()
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # 提升并发读写性能
    return conn


def init_db() -> None:
    """
    初始化数据库。

    检测 DATA_DIR/whisper.db 是否存在：
    - 不存在：创建目录并建表，日志提示「数据库已初始化」
    - 已存在：验证表结构，日志提示「使用已有数据库」
    """
    db_path = get_db_path()
    is_new = not db_path.exists()

    _ensure_data_dir()

    conn = _get_connection()
    try:
        conn.execute(CREATE_TASKS_TABLE_SQL)
        conn.commit()

        if is_new:
            logger.info("数据库已初始化: {}", db_path)
        else:
            logger.info("使用已有数据库: {}", db_path)
    finally:
        conn.close()


def create_task(task_id: str, original_filename: str, language: Optional[str] = None) -> dict:
    """
    创建新任务记录。

    Returns:
        包含任务基本信息的字典
    """
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO tasks (id, original_filename, status, language, created_at) VALUES (?, ?, 'pending', ?, ?)",
            (task_id, original_filename, language, now),
        )
        conn.commit()
        return {
            "id": task_id,
            "original_filename": original_filename,
            "status": "pending",
            "language": language,
            "created_at": now,
        }
    finally:
        conn.close()


def update_task_processing(task_id: str) -> None:
    """将任务状态更新为 processing"""
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE tasks SET status = 'processing' WHERE id = ?",
            (task_id,),
        )
        conn.commit()
    finally:
        conn.close()


def update_task_completed(
    task_id: str,
    text: str,
    segments: list[dict],
    language: str,
) -> None:
    """将任务标记为完成，保存转写结果"""
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            """UPDATE tasks
               SET status = 'completed', text = ?, segments_json = ?, language = ?, completed_at = ?
               WHERE id = ?""",
            (text, json.dumps(segments, ensure_ascii=False), language, now, task_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_task_failed(task_id: str, error_message: str) -> None:
    """将任务标记为失败，记录错误信息"""
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE tasks SET status = 'failed', error_message = ?, completed_at = ? WHERE id = ?",
            (error_message, now, task_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_task(task_id: str) -> Optional[dict]:
    """
    获取单个任务详情。

    Returns:
        任务字典，不存在时返回 None
    """
    conn = _get_connection()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return _row_to_dict(row)
    finally:
        conn.close()


def list_tasks(limit: int = 100, offset: int = 0) -> list[dict]:
    """获取任务列表（按创建时间倒序）"""
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [_row_to_dict(row) for row in rows]
    finally:
        conn.close()


def delete_task(task_id: str) -> bool:
    """
    删除任务记录。

    Returns:
        True 表示删除成功，False 表示任务不存在
    """
    conn = _get_connection()
    try:
        cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict:
    """将 SQLite Row 转换为字典，反序列化 segments_json"""
    d = dict(row)
    # 将 segments_json 字符串反序列化为列表
    if d.get("segments_json"):
        try:
            d["segments"] = json.loads(d["segments_json"])
        except (json.JSONDecodeError, TypeError):
            d["segments"] = []
    else:
        d["segments"] = []
    # 移除内部字段
    d.pop("segments_json", None)
    return d
