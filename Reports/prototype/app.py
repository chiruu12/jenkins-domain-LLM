import streamlit as st
import os
from pathlib import Path
from pipeline import run_diagnosis_pipeline
from dotenv import load_dotenv
import time

load_dotenv()

st.set_page_config(
    page_title="Jenkins AI Diagnoser",
    page_icon="🤖",
    layout="wide"
)

st.markdown("""
    <style>
        /* Target the h3 elements created by st.markdown */
        div[data-testid="stMarkdownContainer"] h3 {
            font-size: 1.2em;
            font-weight: bold;
        }
    </style>
""", unsafe_allow_html=True)

STREAMLIT_WORKSPACE_DIR = "streamlit_workspace"
Path(STREAMLIT_WORKSPACE_DIR).mkdir(exist_ok=True)

if "messages" not in st.session_state:
    st.session_state.messages = [{
        "role": "assistant",
        "content": "Hello! I'm the Jenkins AI Diagnosis Assistant. Please upload your build log and any relevant workspace files using the sidebar to begin."
    }]

with st.sidebar:
    st.image(
        "https://w7.pngwing.com/pngs/180/365/png-transparent-jenkins-devops-continuous-integration-software-development-installation-selenium-text-hand-logo.png",
        use_container_width=True
    )
    st.header("Configuration")

    uploaded_log_file = st.file_uploader(
        label="Upload Build Log",
        type=None
    )

    uploaded_workspace_files = st.file_uploader(
        label="Upload Workspace Files (Optional)",
        help="Upload supporting files like build.xml, pom.xml, or Jenkinsfile.",
        accept_multiple_files=True
    )

    enable_dual_agent = st.toggle(
        "Enable Dual Agent Correction Mode",
        value=True,
        help="A Critic agent reviews the diagnosis for higher quality results."
    )

st.title("Jenkins AI Diagnosis Assistant")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask me to start the diagnosis."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if not uploaded_log_file:
            response = "I cannot start without a log file. Please upload one using the sidebar."
            st.markdown(response)
        else:
            with st.spinner("The AI agents are analyzing the build... This may take a moment."):
                for f in uploaded_workspace_files:
                    file_path = Path(STREAMLIT_WORKSPACE_DIR) / f.name
                    file_path.write_bytes(f.getbuffer())

                log_content = uploaded_log_file.getvalue().decode("utf-8")

                final_report = run_diagnosis_pipeline(
                    raw_log=log_content,
                    workspace_path=STREAMLIT_WORKSPACE_DIR,
                    enable_self_correction=enable_dual_agent
                )
                response = final_report

                for item in Path(STREAMLIT_WORKSPACE_DIR).iterdir():
                    item.unlink()


            def response_streamer(report):
                for word in report.split():
                    yield word + " "
                    time.sleep(0.02)


            st.write_stream(response_streamer(response))

    st.session_state.messages.append({"role": "assistant", "content": response})
