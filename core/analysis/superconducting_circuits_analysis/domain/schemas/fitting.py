from typing import Literal

from pydantic import BaseModel, Field

# === Mode Fitting Models ===


class ModeFitSeries(BaseModel):
    L_jun: list[float] = Field(..., description="Josephson inductance values")
    Freq: list[float] = Field(..., description="Frequency values")


class ModeFitParams(BaseModel):
    Ls_nH: float = Field(..., description="Series inductance in nH")
    C_eff_pF: float = Field(..., description="Effective capacitance in pF")


class ModeFitMetrics(BaseModel):
    RMSE: float = Field(..., description="Root Mean Square Error of the fit")


class ModeFitSuccess(BaseModel):
    status: Literal["success"] = "success"
    params: ModeFitParams
    metrics: ModeFitMetrics
    raw_data: ModeFitSeries
    fit_curve: ModeFitSeries


class ModeFitFailure(BaseModel):
    status: Literal["failed"] = "failed"
    reason: str


ModeFitResult = ModeFitSuccess | ModeFitFailure
FitResultsByMode = dict[str, ModeFitResult]


# === Y11 Fitting Models ===


class Y11FitParams(BaseModel):
    Ls1_nH: float
    Ls2_nH: float
    C_pF: float


class Y11FitMetrics(BaseModel):
    RMSE: float


class Y11FitSeries(BaseModel):
    freq_ghz: list[float]
    imag_y: list[float]
    L_jun: list[float]


class Y11FitSuccess(BaseModel):
    status: Literal["success"] = "success"
    params: Y11FitParams
    metrics: Y11FitMetrics
    raw_data: Y11FitSeries
    fit_curve: Y11FitSeries


class Y11FitFailure(BaseModel):
    status: Literal["failed"] = "failed"
    reason: str


Y11FitResult = Y11FitSuccess | Y11FitFailure


# === Analysis Entry ===


class AnalysisEntry(BaseModel):
    filename: str
    fits: dict[str, ModeFitResult] = Field(default_factory=dict)
