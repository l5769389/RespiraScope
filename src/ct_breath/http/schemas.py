from typing import Optional

from pydantic import BaseModel, Field


class FilterConfig(BaseModel):
    low_bpm: float = Field(default=6, ge=1, le=50, description="Low breath-rate cutoff in BPM")
    high_bpm: float = Field(default=40, ge=1, le=50, description="High breath-rate cutoff in BPM")
    lowpass_cutoff: float = Field(default=6 / 60, ge=0.01, le=20.0, description="Low cutoff in Hz")
    highpass_cutoff: float = Field(default=40 / 60, ge=0.01, le=20.0, description="High cutoff in Hz")
    order: int = Field(default=1, ge=1, le=5, description="Filter order")
    sampling_rate: int = Field(default=50, description="Sampling rate in Hz")
    moving_avg_window: int = Field(default=3, ge=1, le=10, description="Moving average window")
    gaussian_sigma: float = Field(default=1, ge=0.1, le=100.0, description="Gaussian smoothing sigma")
    min_peak_distance: int = Field(default=15, ge=5, le=50, description="Minimum peak distance in samples")
    peak_threshold_ratio: float = Field(default=0.3, ge=0.1, le=1.0, description="Adaptive peak threshold ratio")
    prominence: float = Field(default=1.0, ge=0.0, le=10.0, description="Peak prominence")
    auto_peak_detection: bool = Field(default=True, description="Enable adaptive peak/valley detection")
    confirm_realtime_events: bool = Field(
        default=False,
        description="Delay realtime peak/valley output until a short future window confirms it",
    )
    confirmation_delay_points: int = Field(
        default=12,
        ge=0,
        le=200,
        description="Realtime confirmation delay in samples",
    )
    data_gap_reset_points: int = Field(
        default=25,
        ge=1,
        le=500,
        description="Sequence gap that resets realtime peak/valley detection",
    )
    gap_warmup_points: int = Field(
        default=75,
        ge=0,
        le=1000,
        description="Minimum samples to wait after a data gap before realtime peak/valley detection",
    )
    restore_baseline: bool = Field(default=True, description="Restore baseline after filtering")


class ApplyFilterConfig(BaseModel):
    filter_config: FilterConfig = Field(default_factory=FilterConfig)
    raw_data: list[list[int | float]] = Field(default_factory=list)


class SaveBreathConfig(BaseModel):
    folder_path: Optional[str] = Field(default=r"D:/ct/breath-file")


class SocketClientStatus(BaseModel):
    host: str
    port: int
    running: bool
    connected: bool
    received_count: int
    last_error: Optional[str] = None
    last_connected_at: Optional[float] = None
    last_disconnected_at: Optional[float] = None
    last_received_at: Optional[float] = None
    seconds_since_last_data: Optional[float] = None


class DataReceiverStatus(BaseModel):
    sensor_host: str
    sensor_port: int
    sequence_number: int
    received_count: int
    last_data_at: Optional[float] = None
    seconds_since_last_data: Optional[float] = None
    socket: SocketClientStatus


class QueueStatus(BaseModel):
    raw: int
    filtered: int
    peaks: int
    valleys: int
    metrics: int


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


class StreamStatus(BaseModel):
    started: bool
    receiver: DataReceiverStatus
    queues: QueueStatus
    record: RecordRuntimeStatus
    filter_config: FilterConfig


class StreamStatusResponse(BaseModel):
    code: int = 1
    status: str = "success"
    data: StreamStatus


class MockBreathConfigRequest(BaseModel):
    scenario: Optional[str] = Field(default=None)
    bpm: Optional[float] = Field(default=None, ge=3, le=60)
    amplitude: Optional[float] = Field(default=None, ge=0, le=500)
    baseline: Optional[float] = Field(default=None, ge=0, le=1000)
    noise: Optional[float] = Field(default=None, ge=0, le=200)
    drift: Optional[float] = Field(default=None, ge=0, le=200)
    irregularity: Optional[float] = Field(default=None, ge=0, le=1)
    apnea_interval_sec: Optional[float] = Field(default=None, ge=0, le=300)
    apnea_duration_sec: Optional[float] = Field(default=None, ge=0, le=120)
    artifact_chance: Optional[float] = Field(default=None, ge=0, le=1)
    artifact_amplitude: Optional[float] = Field(default=None, ge=0, le=1000)
    sample_interval_ms: Optional[int] = Field(default=None, ge=5, le=1000)


class MockBreathPreviewRequest(MockBreathConfigRequest):
    seconds: float = Field(default=30, ge=1, le=300)
    sampling_rate: int = Field(default=50, ge=5, le=200)


def normalize_filter_config(config: FilterConfig) -> FilterConfig:
    config.lowpass_cutoff = config.low_bpm / 60
    config.highpass_cutoff = config.high_bpm / 60
    return config
