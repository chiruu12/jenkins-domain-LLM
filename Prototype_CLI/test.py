import pytest
import pytest_asyncio
import shutil
import asyncio
from tools.knowledge_base import CoreLightRAGManager, KnowledgeBaseTools
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


async def test_initialization(rag_manager: CoreLightRAGManager):
    assert rag_manager is not None
    assert rag_manager.is_initialized is True
    assert rag_manager.rag_instance is not None


async def test_store_and_query(rag_manager: CoreLightRAGManager):
    doc_id = "jenkins-heap-error"
    doc_content = "To fix a Java heap space error in Jenkins, increase the -Xmx value in the JVM arguments."
    query = "How do you solve heap space issues?"

    await rag_manager.store_text(text_content=doc_content, document_id=doc_id)

    facade_tool = KnowledgeBaseTools(core_manager=rag_manager)
    response = await facade_tool.query_knowledge_base(query=query)

    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 10
    response_lower = response.lower()
    assert "heap" in response_lower
    assert "xmx" in response_lower
    assert "jvm" in response_lower
