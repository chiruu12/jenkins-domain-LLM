from data_models import (
    CritiqueReport, DiagnosisReport,
    InteractiveClarification, LearningReport,
    QuickSummaryReport, RoutingDecision
)


ROUTING_EXAMPLE = RoutingDecision(
    failure_category="CONFIGURATION_ERROR"
).model_dump_json(indent=2)

DIAGNOSIS_EXAMPLE = DiagnosisReport(
    root_cause="The build failed due to a syntax error in the `Jenkinsfile` at the 'Build' stage.",
    evidence={
        "Error Log from Jenkins Output": "org.codehaus.groovy.control.MultipleCompilationErrorsException: startup failed:\nWorkflowScript: 15: unexpected token: } @ line 15, column 5.",
        "Contents of Jenkinsfile line 15": "    }\n   }\n  }\n }"
    },
    suggested_fix=[
        "Open the `Jenkinsfile`.",
        "Navigate to line 15 and remove the extraneous closing curly brace `}`.",
        "Commit the corrected file and re-run the Jenkins build."
    ],
    confidence="high",
    reasoning="The error log explicitly points to a compilation error in the Jenkinsfile, a clear indicator of a configuration issue."
).model_dump_json(indent=2)

CRITIQUE_EXAMPLE = CritiqueReport(
    is_approved=False,
    critique="The diagnosis correctly identifies a test failure but lacks specific evidence. The `evidence` field should quote the exact test report file (e.g., from `target/surefire-reports`) instead of just the generic log output.",
    confidence="high",
    reasoning="The diagnosis was rejected because it made a correct claim without providing the strongest possible evidence available in the workspace."
).model_dump_json(indent=2)

QUICK_SUMMARY_EXAMPLE = QuickSummaryReport(
    summary="The build likely failed due to a test assertion error in the `com.mycompany.app.AppTest` class.",
    confidence="medium"
).model_dump_json(indent=2)

INTERACTIVE_EXAMPLE = InteractiveClarification(
    question="I've detected a `compilation error`. To proceed, which area should I investigate first?",
    suggested_actions=["Examine `changelog.xml` for recent code changes", "Inspect `pom.xml` for dependency issues"]
).model_dump_json(indent=2)

LEARNING_EXAMPLE = LearningReport(
    concept_explanation="A `DependencyConflictException` in a Maven build occurs when two or more of your project's dependencies rely on different, incompatible versions of the same third-party library. Maven's dependency resolution mechanism can only pick one version, which may not satisfy the requirements of all other dependencies, leading to the conflict.",
    documentation_links=[
        "https://maven.apache.org/guides/introduction/introduction-to-the-dependency-mechanism.html#transitive-dependencies",
        "https://www.jenkins.io/doc/book/pipeline/jenkinsfile/"
    ]
).model_dump_json(indent=2)

QUICK_SUMMARY_CRITIQUE_EXAMPLE = CritiqueReport(
    is_approved=False,
    critique="The report is not a brief summary. It includes a multi-line evidence block and a suggested fix, which violates the core requirement of this mode. The output should be only a one or two-sentence summary.",
    confidence="high",
    reasoning="The agent failed to follow the output format constraints for Quick Summary mode by providing excessive detail."
).model_dump_json(indent=2)

INTERACTIVE_CRITIQUE_EXAMPLE = CritiqueReport(
    is_approved=False,
    critique="The agent did not ask a question. Instead, it provided a direct root cause analysis, which is incorrect for Interactive Debugging mode. The goal is to ask a clarifying question to guide the user.",
    confidence="high",
    reasoning="The agent's response did not match the required conversational and inquisitive objective of the interactive mode."
).model_dump_json(indent=2)