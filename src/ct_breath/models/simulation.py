"""Simulation data contracts shared by services and adapters."""
from typing import Optional
from pydantic import BaseModel, Field


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
