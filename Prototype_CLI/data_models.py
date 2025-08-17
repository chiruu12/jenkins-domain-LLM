from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Type
import os
from pydantic import BaseModel, Field, DirectoryPath
from tools.knowledge_base import LightRAGConfig

class OperatingMode(str, Enum):
    STANDARD = "Standard Diagnosis"
    QUICK_SUMMARY = "Quick Summary"
    INTERACTIVE = "Interactive Debugging"
    LEARNING = "Learning Mode"

class ProviderConfig(BaseModel):
    model_class: Optional[Type[Any]]
    default_model: str
    requires_args: List[str] = Field(default_factory=list)

class ModelConfig(BaseModel):
    provider_key: str
    model_key: str
    model_id: str

class LLMCatalog(BaseModel):
    providers: Dict[str, ProviderConfig]
    mappings: Dict[str, Dict[str, str]]

    def get_provider_names(self) -> List[str]:
        return list(self.providers.keys())

    def get_model_keys_for_provider(self, provider_key: str) -> List[str]:
        return list(self.mappings.get(provider_key, {}).keys())


class RoutingDecision(BaseModel):
    failure_category: Literal[
        "CONFIGURATION_ERROR", "TEST_FAILURE", "DEPENDENCY_ERROR", "INFRA_FAILURE", "UNKNOWN"
    ] = Field(description="The single, most likely category for the build failure.")
    relevant_log_snippets: List[str] = Field(
        description="A list of the most critical log lines (5-10 lines) that directly indicate the reason for the failure."
    )

class DiagnosisReport(BaseModel):
    root_cause: str = Field(description="A clear, one-to-two sentence explanation of the primary reason for the failure.")
    evidence: Dict[str, str] = Field(description="A dictionary where keys are descriptive titles and values are multi-line code blocks of evidence.")
    suggested_fix: List[str] = Field(description="A clear, step-by-step list of actions to resolve the issue.")
    confidence: Literal["low", "medium", "high"] = Field(description="An assessment of the diagnosis confidence.")
    reasoning: str = Field(description="A brief explanation of the thought process behind the diagnosis.")

class CritiqueReport(BaseModel):
    is_approved: bool = Field(description="A boolean flag that is true if the report is approved, and false otherwise.")
    critique: str = Field(description="Constructive feedback for the Diagnostician if the report is not approved. If approved, this states 'Approved'.")
    confidence: Literal["low", "medium", "high"] = Field(description="An assessment of the critique's confidence.")
    reasoning: str = Field(description="A brief explanation for why the report was approved or rejected.")

class QuickSummaryReport(BaseModel):
    summary: str = Field(description="A one or two-sentence summary of the most likely root cause.")
    confidence: Literal["low", "medium", "high"] = Field(description="An assessment of the diagnosis confidence.")

class InteractiveClarification(BaseModel):
    question: str = Field(description="A question to ask the user to help narrow down the problem.")
    suggested_actions: List[str] = Field(description="A list of suggested actions or areas to investigate.", default_factory=list)

class LearningReport(BaseModel):
    concept_explanation: str = Field(description="A detailed explanation of the requested Jenkins concept, written for a beginner.")
    documentation_links: List[str] = Field(description="A list of relevant URLs to official Jenkins documentation or related resources.")

class TokenUsageLog(BaseModel):
    """Structured model for token usage in a single LLM call."""
    call_input_tokens: int
    call_output_tokens: int
    cumulative_input_tokens: int
    cumulative_output_tokens: int

class LLMRequestLog(BaseModel):
    """Structured log for a request sent to an LLM."""
    type: Literal["request"] = "request"
    model_id: str
    tools: Optional[List[str]] = None
    messages: List[Dict[str, Any]]

class LLMResponseLog(BaseModel):
    type: Literal["response"] = "response"
    model_id: str
    final_content: Optional[Any]
    token_usage: TokenUsageLog
    full_message_history: Optional[List[Dict[str, Any]]] = None

class LLMErrorLog(BaseModel):
    """Structured log for an error during an LLM interaction."""
    type: Literal["error"] = "error"
    model_id: str
    error_message: str
    raw_response: Optional[str] = None
