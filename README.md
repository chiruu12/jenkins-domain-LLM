# jenkins-domain-LLM (GSoC 2025)

**Project:** Jenkins Domain specific LLM based on actual Jenkins usage using ci.jenkins.io data

## Project Overview

This repository contains the development work for the Google Summer of Code 2025 project focused on building a LLM-powered assistant to diagnose Jenkins build failures.

The initial proposal centered on fine-tuning a domain-specific LLM. However, the project has since evolved to prioritize a more flexible and robust **universal agentic architecture**. This approach lowers the barrier to entry for users and developers, supports a wider range of models (including any future fine-tuned Jenkins LLM), and provides a more extensible foundation for future development. The core goal remains the same: to create a powerful tool that makes debugging Jenkins failures faster and more intuitive.



## Project Structure
```
.
├── Prototype/
│   ├── prompts/                # Contains markdown templates for agent instructions.
│   ├── streamlit_workspace/    # Temporary directory for Streamlit file uploads.
│   ├── Test_files/             # Contains examples for review.
│   │   └── 1/                  # Example Case 1
│   │       ├── input/          #   - All input files (logs, xml, etc.) for the case.
│   │       └── output.md       #   - The agent's generated output for this case.
│   │   └── ...                 # (and so on for other cases)
│   ├── agents.py               # Contains factory functions for creating all agents.
│   ├── app.py                  # Main Streamlit application for the UI.
│   ├── config.py               # Centralized configuration for the application.
│   ├── data_models.py          # Pydantic models for structured agent outputs.
│   ├── pipeline.py             # Orchestrates the diagnostic workflow.
│   ├── Readme.md               # Specific README for the prototype.
│   ├── requirements.txt        # Python dependencies for the project.
│   ├── sanitizer.py            # Utility for cleaning and preprocessing raw log files.
│   └── tools.py                # Defines toolkits available to agents.
│
└── Reports/
    ├── agentic_architectures/  # Diagrams and puml code on the agentic architecture.
    └── prototype/              # Code related to the prototype development.
```
## Development

An initial pull request has been submitted to the Jenkins project to establish the baseline for this new agentic architecture.

*   **PR:** [#1](https://github.com/chiruu12/jenkins-domain-LLM/pull/1)
*   **Title:** "Adding Prototype"
*   **Status:** Awaiting Mentor Review

This PR includes:
*   The fully functional prototype of the multi-agent diagnostic system detailed in this repository.
*   The refactored code demonstrating the modular agent factories and externalized prompt management.
*   A set of initial diagnostic examples (input logs/build files and their corresponding agent generated outputs). These are baseline results intended for mentor review. The feedback from this review will be used for iteratively improving the agent's prompts and overall performance.
