## Prototype Overview
This prototype is made to demonstrate a streamlined AI agent pipeline for diagnosing software build failures. It leverages OpenRouter's API to create a modular, extensible system that can be easily adapted for various use cases.

1.  **Input & UI:** A Streamlit web interface allows users to upload a build log and associated workspace files.
2.  **Log Sanitization:** Raw logs are cleaned to remove noise (timestamps, ANSI codes), preparing the data for the AI.
3.  **Failure Routing:** A specialized "router" agent classifies the failure into a predefined category (e.g., `CONFIGURATION_ERROR`, `TEST_FAILURE`).
4.  **Specialist Diagnosis:** Based on the classification, a dedicated specialist agent is activated to perform an in-depth analysis using tools to inspect workspace files.
5.  **Self-Correction Loop:** An optional "critic" agent reviews the diagnosis. If the report is flawed, it provides feedback to the specialist agent, which then refines its analysis and tries again.
6.  **Final Report:** A structured, user-friendly markdown report detailing the root cause, evidence, and a suggested fix is generated.


## How to Run

1.  **Set up Environment:** Create a `.env` file in the root directory and add your API key:
    ```
    OPENROUTER_API_KEY="your_api_key_here"
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Application:**
    ```bash
    streamlit run app.py
    ```