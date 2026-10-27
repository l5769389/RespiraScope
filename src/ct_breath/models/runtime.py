"""Runtime data contracts shared by services and adapters."""
from typing import Optional
from pydantic import BaseModel, Field
from .filtering import FilterConfig


class SocketClientStatus(BaseModel):
    host: str
    port: int
    running: bool
    connected: bool
    received_count: int
    last_error: Optional[str] = None
    last_connected_at: Optional[str] = None
    last_disconnected_at: Optional[str] = None
    last_received_at: Optional[str] = None
    seconds_since_last_data: Optional[float] = None



class DataReceiverStatus(BaseModel):
    sensor_host: str
    sensor_port: int
    sequence_number: int
    received_count: int
    last_data_at: Optional[str] = None
    seconds_since_last_data: Optional[float] = None
    socket: SocketClientStatus



class QueueStatus(BaseModel):
    raw: int
    filtered: int
    peaks: int
    valleys: int
    metrics: int
    signal_quality: int



class QueueStats(BaseModel):
    dropped: dict[str, int]
    high_watermark: dict[str, int]



class RecordRuntimeStatus(BaseModel):
    pre_points: int
    post_points: int
    recording: bool
    post_recording: bool
    record_complete: bool
    record_start_sequence: Optional[int] = None
    record_end_sequence: Optional[int] = None
    capture_start_sequence: Optional[int] = None
    capture_end_sequence: Optional[int] = None
    scan_active: bool = False
    active_scan: Optional[dict] = None
    scans: list[dict] = Field(default_factory=list)



class StreamStatus(BaseModel):
    started: bool
    state: str = "idle"
    last_error: Optional[str] = None
    tasks: dict[str, dict[str, bool]] = Field(default_factory=dict)
    receiver: DataReceiverStatus
    queues: QueueStatus
    queue_stats: QueueStats
    record: RecordRuntimeStatus
    signal_quality: dict = Field(default_factory=dict)
    filter_config: FilterConfig



class StreamStatusResponse(BaseModel):
    code: int = 1
    status: str = "success"
    data: StreamStatus
