import pytest
import pytest_asyncio
import shutil
import asyncio
from pathlib import Path

import config
from agents import get_specialist_agent, get_router_agent
from tools.knowledge_base import CoreLightRAGManager, KnowledgeBaseTools
from tools.jenkins_workspace import JenkinsWorkspaceTools
from tools.log_access import LogAccessTools
from data_models import LightRAGConfig

pytestmark = pytest.mark.asyncio



@pytest_asyncio.fixture(scope="module")
async def rag_manager(tmp_path_factory):
    test_workspace_dir = tmp_path_factory.mktemp("rag_workspace")
    print(f"\nTest RAG workspace: {test_workspace_dir}")

    config = LightRAGConfig(working_dir=test_workspace_dir)
    manager = CoreLightRAGManager(config=config)

    await manager.initialize()

    yield manager

    await manager.finalize()
    tasks = [task for task in asyncio.all_tasks() if task is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    shutil.rmtree(test_workspace_dir)



@pytest.fixture
def setup_test_prompts(tmp_path: Path, monkeypatch):
    prompts_dir = tmp_path / "prompts"
    tools_prompts_dir = prompts_dir / "tools"
    tools_prompts_dir.mkdir(parents=True)

    monkeypatch.setattr(config, "PROMPTS_DIR", prompts_dir)

    main_prompt_content = """### Main Goal
        Test prompt.
        
        ### Tool Usage
        {tool_usage}
        
        ### Example
        {example_json}
        """

    (prompts_dir / "config_error.md").write_text(main_prompt_content)
    (prompts_dir / "router.md").write_text(main_prompt_content)

    (tools_prompts_dir / "jenkins_workspace_tools.md").write_text("### JWS Instructions\n- List then read.")
    (tools_prompts_dir / "log_access_tools.md").write_text("### Log Access Instructions\n- Use to get full log.")

    yield prompts_dir


async def test_rag_initialization(rag_manager: CoreLightRAGManager):
    assert rag_manager is not None
    assert rag_manager.is_initialized is True
    assert rag_manager.rag_instance is not None


async def test_rag_store_and_query(rag_manager: CoreLightRAGManager):
    doc_id = "jenkins-heap-error"
    doc_content = "To fix a Java heap space error in Jenkins, increase the -Xmx value in the JVM arguments."
    query = "How do you solve heap space issues?"

    facade_tool = KnowledgeBaseTools(prompt_dir=str(Path("prompts")), core_manager=rag_manager)

    await rag_manager.store_text(text_content=doc_content, document_id=doc_id)

    response = await facade_tool.query_knowledge_base(query=query)

    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 10
    response_lower = response.lower()
    assert "heap" in response_lower
    assert "xmx" in response_lower
    assert "jvm" in response_lower


def test_specialist_agent_prompt_assembly(setup_test_prompts):
    prompts_dir = setup_test_prompts

    jws_tool = JenkinsWorkspaceTools(base_directory_path=".", prompt_dir=str(prompts_dir))
    log_tool = LogAccessTools(prompt_dir=str(prompts_dir))
    kb_tool = KnowledgeBaseTools(prompt_dir=str(prompts_dir), core_manager=None)

    agent = get_specialist_agent(
        agent_type="CONFIGURATION_ERROR",
        tools=[jws_tool, log_tool, kb_tool]
    )

    final_prompt = agent.instructions[0]

    assert "# Tool Usage" in final_prompt
    assert "### JWS Instructions" in final_prompt
    assert "- List then read." in final_prompt
    assert "### Log Access Instructions" in final_prompt
    assert "- Use to get full log." in final_prompt
    assert "{tool_usage}" not in final_prompt
    assert "{example_json}" not in final_prompt


def test_router_agent_removes_tool_section(setup_test_prompts):
    agent = get_router_agent()

    final_prompt = agent.instructions[0]

    assert "### Tool Usage" not in final_prompt
    assert "{tool_usage}" not in final_prompt
    assert "### Main Goal" in final_prompt
    assert "{example_json}" not in final_prompt
