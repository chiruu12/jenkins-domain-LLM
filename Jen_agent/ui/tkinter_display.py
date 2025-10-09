import tkinter as tk
from tkinter import scrolledtext

from pydantic import BaseModel

from data_models import (
    DiagnosisReport,
    QuickSummaryReport,
    LearningReport,
    InteractiveClarification,
    CritiqueReport
)


def configure_widget_tags(widget: scrolledtext.ScrolledText):
    """Sets up the text tags for styling the output."""
    widget.tag_configure("h3", font=("Segoe UI", 13, "bold"), spacing1=5, spacing3=5)
    widget.tag_configure("bold", font=("Segoe UI", 12, "bold"))
    widget.tag_configure("italic", font=("Segoe UI", 12, "italic"))
    widget.tag_configure("code", font=("Courier New", 11), background="#2E2E2E", wrap="word")
    widget.tag_configure("error", foreground="red")
    widget.tag_configure("user_prompt", foreground="#599258", font=('Segoe UI', 13, 'bold'))
    widget.tag_configure("assistant_response", foreground="#CECABF", font=('Segoe UI', 13))


def render_report_in_widget(report_object: BaseModel, widget: scrolledtext.ScrolledText):
    """Renders a Pydantic model object into a styled ScrolledText widget."""
    widget.config(state=tk.NORMAL)

    if isinstance(report_object, DiagnosisReport):
        widget.insert(tk.END, "Diagnosis Report\n", "h3")
        widget.insert(tk.END, "Root Cause: ", "bold")
        widget.insert(tk.END, f"{report_object.root_cause}\n\n", "assistant_response")
        if report_object.evidence:
            widget.insert(tk.END, "Evidence:\n", "bold")
            for title, evidence_text in report_object.evidence.items():
                widget.insert(tk.END, f"  {title}:\n", "italic")
                widget.insert(tk.END, f"{evidence_text}\n\n", "code")
        if report_object.suggested_fix:
            widget.insert(tk.END, "Suggested Fix:\n", "bold")
            for i, step in enumerate(report_object.suggested_fix, 1):
                widget.insert(tk.END, f"{i}. {step}\n", "assistant_response")
        widget.insert(tk.END, f"\nConfidence: {report_object.confidence.title()}\n", "italic")

    elif isinstance(report_object, QuickSummaryReport):
        widget.insert(tk.END, "Quick Summary\n", "h3")
        widget.insert(tk.END, f"{report_object.summary}\n", "assistant_response")
        widget.insert(tk.END, f"\nConfidence: {report_object.confidence.title()}\n", "italic")

    elif isinstance(report_object, LearningReport):
        widget.insert(tk.END, "Learning Report\n", "h3")
        widget.insert(tk.END, f"{report_object.concept_explanation}\n\n", "assistant_response")
        if report_object.documentation_links:
            widget.insert(tk.END, "Further Reading:\n", "bold")
            for link in report_object.documentation_links:
                widget.insert(tk.END, f"- {link}\n", "assistant_response")

    elif isinstance(report_object, InteractiveClarification):
        widget.insert(tk.END, "Question\n", "h3")
        widget.insert(tk.END, f"{report_object.question}\n\n", "assistant_response")
        if report_object.suggested_actions:
            widget.insert(tk.END, "Suggested Actions:\n", "bold")
            for action in report_object.suggested_actions:
                widget.insert(tk.END, f"- {action}\n", "assistant_response")

    elif isinstance(report_object, dict) and "error" in report_object:
        widget.insert(tk.END, "An Error Occurred\n", "h3")
        widget.insert(tk.END, f"{report_object.get('error')}\n", "error")
        if details := report_object.get("details"):
            widget.insert(tk.END, f"Details: {details}\n", "error")

    else:
        widget.insert(tk.END, f"{report_object}\n", "assistant_response")

    widget.insert(tk.END, "\n\n")
    widget.config(state=tk.DISABLED)
    widget.see(tk.END)
