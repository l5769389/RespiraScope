from typing import Annotated, Literal, Optional

from pydantic import AfterValidator, BaseModel, Field, FiniteFloat, model_validator


def validate_sample_order(points):
    if any(right[0] <= left[0] for left, right in zip(points, points[1:])):
        raise ValueError("Sample sequence numbers must be strictly increasing; duplicates are not allowed")
    return points


SampleSeries = Annotated[
    list[tuple[Annotated[int, Field(ge=0, strict=True)], FiniteFloat]],
    AfterValidator(validate_sample_order),
]


class FilterConfig(BaseModel):
    processing_mode: Literal["time", "amplitude"] = "time"
    offline_filter: Literal["bandpass", "baseline_lowpass"] = "bandpass"
    lowpass_order: int = Field(default=4, ge=1, le=5, description="Baseline-preserving offline low-pass order")
    bandpass_mode: Literal["preset", "custom"] = "preset"
    low_bpm: float = Field(default=6, ge=1, le=50, description="Low breath-rate cutoff in BPM")
    high_bpm: float = Field(default=40, ge=1, le=50, description="High breath-rate cutoff in BPM")
    lowpass_cutoff: float = Field(default=6 / 60, ge=0.01, le=20.0, description="Low cutoff in Hz")
    highpass_cutoff: float = Field(default=40 / 60, ge=0.01, le=20.0, description="High cutoff in Hz")
    order: int = Field(default=1, ge=1, le=5, description="Filter order")
    sampling_rate: int = Field(default=50, gt=0, description="Sampling rate in Hz")
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

    @model_validator(mode="after")
    def validate_bandpass(self):
        low, high = self.lowpass_cutoff, self.highpass_cutoff
        if self.bandpass_mode == "preset":
            low, high = (0.03, 2.0) if self.processing_mode == "amplitude" else (self.low_bpm / 60, self.high_bpm / 60)
            if self.offline_filter == 'baseline_lowpass':
                high = 2.0
        if self.offline_filter == 'baseline_lowpass':
            if not 0 < high < self.sampling_rate / 2:
                raise ValueError("Low-pass cutoff must be below half the sampling rate")
            return self
        if not 0 < low < high < self.sampling_rate / 2:
            raise ValueError("Bandpass must satisfy 0 < lower < upper < sampling_rate / 2")
        return self


class ApplyFilterConfig(BaseModel):
    filter_config: FilterConfig = Field(default_factory=FilterConfig)
    raw_data: SampleSeries = Field(default_factory=list)
    record_start_sequence: Annotated[int, Field(ge=0, strict=True)] | None = None
    record_end_sequence: Annotated[int, Field(ge=0, strict=True)] | None = None

    @model_validator(mode='after')
    def validate_record_range(self):
        start, end = self.record_start_sequence, self.record_end_sequence
        if (start is None) != (end is None) or (start is not None and end < start):
            raise ValueError('Provide both record boundaries with start <= end')
        return self


class InvalidInterval(BaseModel):
    start: FiniteFloat
    end: FiniteFloat
    reason: Literal['spike', 'motion', 'filter_edge', 'gap', 'too_short']

    @model_validator(mode='after')
    def validate_range(self):
        if self.start < 0 or self.end <= self.start:
            raise ValueError('Invalid interval must satisfy 0 <= start < end')
        return self


class DetectPeaksConfig(BaseModel):
    filter_config: FilterConfig = Field(default_factory=FilterConfig)
    filtered_data: SampleSeries = Field(default_factory=list)
    invalid_intervals: list[InvalidInterval] = Field(default_factory=list)


class RecordAnalysisConfig(BaseModel):
    totalBins: Literal[4, 6, 8, 10, 12, 16, 20] = 10
    basis: Literal["time", "amplitude"] = "time"
    amplitudeMode: Literal["free", "fixed"] = "free"
    lower: FiniteFloat | None = None
    upper: FiniteFloat | None = None
    inhaleRising: bool = True

    @model_validator(mode="after")
    def validate_bounds(self):
        if self.basis == "amplitude" and self.amplitudeMode == "fixed":
            if self.lower is None or self.upper is None:
                raise ValueError("Fixed amplitude binning requires lower and upper bounds")
        if self.lower is not None and self.upper is not None and self.lower >= self.upper:
            raise ValueError("lower must be less than upper")
        return self


class SaveBreathConfig(BaseModel):
    folder_path: Optional[str] = Field(default=r"D:/ct/breath-file")
    analysis: RecordAnalysisConfig | None = None


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
    if config.bandpass_mode == "preset":
        config.lowpass_cutoff = 0.03 if config.processing_mode == "amplitude" else config.low_bpm / 60
        config.highpass_cutoff = 2.0 if config.processing_mode == "amplitude" else config.high_bpm / 60
        if config.offline_filter == 'baseline_lowpass':
            config.highpass_cutoff = 2.0
    if config.offline_filter == 'baseline_lowpass':
        config.restore_baseline = True
    return config
