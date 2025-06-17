from pydantic import BaseModel, Field
from typing import Literal

class RoutingDecision(BaseModel):
    failure_category: Literal[
        "CONFIGURATION_ERROR",
        "TEST_FAILURE",
        "DEPENDENCY_ERROR",
        "INFRA_FAILURE",
        "UNKNOWN"
    ] = Field(description="The single, most likely category for the build failure.")

class DiagnosisReport(BaseModel):
    response: str = Field(
        description="The final, user-facing diagnosis report in markdown format."
    )
    reason: str = Field(
        description="A brief, one-sentence explanation of the thought process behind the diagnosis."
    )

class CritiqueReport(BaseModel):
    is_approved: bool = Field(
        description="A boolean flag that is true if the report is approved, and false otherwise."
    )
    critique: str = Field(
        description="Constructive feedback for the Diagnostician if the report is not approved."
                    " If approved, this states 'Approved'."
    )
    reason: str = Field(
        description="A brief explanation for why the report was approved or rejected."
    )