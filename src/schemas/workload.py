from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

class DimensionScore(BaseModel):
    score: int = Field(..., ge=0, le=100, description="0-100 workload intensity score")
    evidence_quotes: List[str] = Field(default_factory=list, description="Direct quotes supporting the score")
    analysis: str = Field(None, description="Explainable reasoning for the score assignment")

class WorkloadScores(BaseModel):
    exam: DimensionScore
    coding: DimensionScore
    team_project: DimensionScore
    reading_essay: DimensionScore
    lab_experiment: DimensionScore


class WorkloadSummary(BaseModel):
    burnout_risk_tags: List[str] = Field(default_factory=list, description="Top 2-3 stress factors, e.g., 'Weekly C++ P-sets'")
    weekly_hours_estimated: float = Field(..., description="Estimated out-of-class hours per week")
    overall_summary: str = Field(..., description="3-line summary of the course workload, including difficulty, grading, and pros/cons")


class WorkloadAnalysis(BaseModel):
    workload_scores: WorkloadScores
    # archetype: WorkloadArchetype
    burnout_risk_tags: List[str] = Field(default_factory=list, description="Top 2-3 stress factors, e.g., 'Weekly C++ P-sets'")
    weekly_hours_estimated: float = Field(..., description="Estimated out-of-class hours per week")
    # summary_reasoning: str = Field(..., description="Explainable summary of why these scores were assigned")
    review_summary_3lines: str = Field(..., description="3-line summary of student reviews (difficulty, grading, pros/cons)")

class WorkloadAnalysis2(BaseModel):
    workload_scores: WorkloadScores
    burnout_risk_tags: List[str] = Field(default_factory=list, description="Top 2-3 stress factors, e.g., 'Weekly C++ P-sets'")
    weekly_hours_estimated: float = Field(..., description="Estimated out-of-class hours per week")
    overall_summary: str = Field(..., description="3-line summary of the course workload, including difficulty, grading, and pros/cons")