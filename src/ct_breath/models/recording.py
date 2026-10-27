"""Recording data contracts shared by services and adapters."""
from typing import Literal, Optional
from pydantic import BaseModel, Field, FiniteFloat, model_validator


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
