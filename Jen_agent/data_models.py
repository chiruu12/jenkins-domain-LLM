from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from datetime import datetime, timezone
from pydantic import BaseModel, Field


class OperatingMode(str, Enum):
    def __new__(cls, value, description=""):
        obj = str.__new__(cls, value)
        obj._value_ = value
        obj.description = description
        return obj

    STANDARD = ("Standard Diagnosis", "Performs a full root cause analysis on a Jenkins log file.")
    QUICK_SUMMARY = ("Quick Summary", "Provides a brief, one-sentence summary of the likely failure reason.")
    INTERACTIVE = ("Interactive Debugging", "Starts a chat session to help you debug a problem step-by-step.")
    LEARNING = ("Learning Mode", "Acts as an expert system to answer your questions about Jenkins.")


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

    def to_display_dict(self) -> Dict[str, Any]:
        return {
            "title": "🕵️ Diagnosis Report",
            "sections": [
                {"key": "Root Cause", "value": self.root_cause, "type": "markdown"},
                {"key": "Evidence", "value": self.evidence, "type": "evidence"},
                {"key": "Suggested Fix", "value": self.suggested_fix, "type": "list"},
                {"key": "Confidence", "value": self.confidence, "type": "key_value"},
                {"key": "Reasoning", "value": self.reasoning, "type": "key_value_italic"},
            ],
        }


class CritiqueReport(BaseModel):
    is_approved: bool = Field(description="A boolean flag that is true if the report is approved, and false otherwise.")
    critique: str = Field(description="Constructive feedback for the Diagnostician if the report is not approved. If approved, this states 'Approved'.")
    confidence: Literal["low", "medium", "high"] = Field(description="An assessment of the critique's confidence.")
    reasoning: str = Field(description="A brief explanation for why the report was approved or rejected.")

    def to_display_dict(self) -> Dict[str, Any]:
        status_emoji = "✅" if self.is_approved else "❌"
        return {
            "title": f"{status_emoji} Critique Report",
            "sections": [
                {"key": "Approved", "value": "Yes" if self.is_approved else "No", "type": "key_value"},
                {"key": "Critique", "value": self.critique, "type": "markdown"},
                {"key": "Confidence", "value": self.confidence, "type": "key_value"},
                {"key": "Reasoning", "value": self.reasoning, "type": "key_value_italic"},
            ],
        }


class QuickSummaryReport(BaseModel):
    summary: str = Field(description="A one or two-sentence summary of the most likely root cause.")
    confidence: Literal["low", "medium", "high"] = Field(description="An assessment of the diagnosis confidence.")

    def to_display_dict(self) -> Dict[str, Any]:
        return {
            "title": "⚡ Quick Summary",
            "sections": [
                {"key": "Summary", "value": self.summary, "type": "markdown"},
                {"key": "Confidence", "value": self.confidence, "type": "key_value"},
            ],
        }


class InteractiveClarification(BaseModel):
    question: str = Field(description="A question to ask the user to help narrow down the problem.")
    suggested_actions: List[str] = Field(description="A list of suggested actions or areas to investigate.", default_factory=list)

    def to_display_dict(self) -> Dict[str, Any]:
        return {
            "title": "💬 Interactive Debugger",
            "sections": [
                {"key": "Question", "value": self.question, "type": "markdown_bold"},
                {"key": "Suggested Actions", "value": self.suggested_actions, "type": "list"},
            ],
        }


class LearningReport(BaseModel):
    concept_explanation: str = Field(description="A detailed explanation of the requested Jenkins concept, written for a beginner.")
    documentation_links: List[str] = Field(description="A list of relevant URLs to official Jenkins documentation or related resources.")

    def to_display_dict(self) -> Dict[str, Any]:
        return {
            "title": "📚 Learning Report",
            "sections": [
                {"key": "Concept Explanation", "value": self.concept_explanation, "type": "markdown"},
                {"key": "Documentation Links", "value": self.documentation_links, "type": "list"},
            ],
        }


class TokenUsageLog(BaseModel):
    call_input_tokens: int
    call_output_tokens: int
    cumulative_input_tokens: int
    cumulative_output_tokens: int

class LLMRequestLog(BaseModel):
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
    type: Literal["error"] = "error"
    model_id: str
    error_message: str
    raw_response: Optional[str] = None

class TokenUsage(BaseModel):
    input_tokens: int
    output_tokens: int


class AgentExecutionRecord(BaseModel):
    agent_id: str
    provider_id: str
    model_id: str
    tools_used: List[str]
    input_prompt: str
    raw_response: str
    parsed_response: Dict[str, Any]
    token_usage: TokenUsage
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserInteractionRecord(BaseModel):
    user_input: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


SessionTurn = Union[AgentExecutionRecord, UserInteractionRecord]


class SessionLog(BaseModel):
    run_id: str
    mode: OperatingMode
    initial_input: str
    session_flow: List[SessionTurn] = Field(default_factory=list)


class SessionSettings(BaseModel):
    provider: str
    chat_model: str
    use_reranker: bool
    use_conversation_memory: bool = True
    reranker_provider: Optional[str] = None
    reranker_model: Optional[str] = None

class ConversationTurn(BaseModel):
    user_input: str
    agent_response: Dict[str, Any]

class BasePipelineContext(BaseModel):
    short_term_history: List[ConversationTurn]
    long_term_memory: List[ConversationTurn]

class InitialLogInput(BasePipelineContext):
    raw_log: str
    enable_self_correction: bool

class InitialInteractiveInput(BasePipelineContext):
    user_input: str

class FollowupInput(BasePipelineContext):
    user_input: str
