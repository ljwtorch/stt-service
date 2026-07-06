from typing import Optional

from pydantic import BaseModel


class Segment(BaseModel):
    """转写分段结果"""

    id: int
    start: float
    end: float
    text: str


class TranscribeResponse(BaseModel):
    """转写接口响应（同步接口）"""

    text: str
    language: str
    segments: list[Segment]


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str
    model: str


class TaskSubmitResponse(BaseModel):
    """异步任务提交响应"""

    task_id: str
    status: str


class TaskStatus(BaseModel):
    """单个任务的状态信息"""

    id: str
    original_filename: str
    status: str  # pending / processing / completed / failed
    language: Optional[str] = None
    text: Optional[str] = None
    segments: Optional[list[dict]] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None


class TaskListResponse(BaseModel):
    """任务列表响应"""

    tasks: list[TaskStatus]
