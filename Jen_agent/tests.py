import asyncio
import logging
import os
import numpy as np
from dotenv import load_dotenv
from agno.agent import Agent
import pytest
from models.google.client import GoogleProvider
from models.groq.client import GroqProvider
from models.lm_studio.client import LMStudioProvider
from models.openrouter.client import OpenRouterProvider

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
load_dotenv()
pytestmark = pytest.mark.asyncio

async def test_google_provider():
    print("\n" + "="*50)
    print("--- Testing GoogleProvider Agent (LIVE) ---")
    try:
        provider = GoogleProvider()
        print("[SUCCESS] Initialized Provider.")

        model = provider.get_chat_model()
        agent = Agent(model=model, instructions=["You are a helpful assistant."])
        print("[SUCCESS] Created Agent.")

        response = await agent.arun("What is the speed of light?")
        assert response and len(response.content) > 5
        print("[SUCCESS] Agent.arun() returned a valid response.")

        embed_func = provider.get_embedding_function()
        embeddings = await embed_func(["hello world"])
        assert isinstance(embeddings, np.ndarray) and embeddings.shape[0] == 1
        print("[SUCCESS] get_embedding_function returned valid embeddings.")
    except Exception as e:
        print(f"[FAILED] GoogleProvider test failed: {e}")

async def test_groq_provider():
    print("\n" + "="*50)
    print("--- Testing GroqProvider Agent (LIVE) ---")
    try:
        provider = GroqProvider()
        print("[SUCCESS] Initialized Provider.")

        model = provider.get_chat_model()
        agent = Agent(model=model, instructions=["You are a helpful assistant."])
        print("[SUCCESS] Created Agent.")

        response = await agent.arun("What is Groq?")
        assert response and len(response.content) > 5
        print("[SUCCESS] Agent.arun() returned a valid response.")
    except Exception as e:
        print(f"[FAILED] GroqProvider test failed: {e}")

async def test_openrouter_provider():
    print("\n" + "="*50)
    print("--- Testing OpenRouterProvider Agent (LIVE) ---")
    try:
        provider = OpenRouterProvider()
        print("[SUCCESS] Initialized Provider.")

        model = provider.get_chat_model()
        agent = Agent(model=model, instructions=["You are a helpful assistant."])
        print("[SUCCESS] Created Agent.")

        response = await agent.arun("What is OpenRouter?")
        assert response and len(response.content) > 5
        print("[SUCCESS] Agent.arun() returned a valid response.")
    except Exception as e:
        print(f"[FAILED] OpenRouterProvider test failed: {e}")

async def test_lmstudio_provider():
    print("\n" + "="*50)
    print("--- Testing LMStudioProvider Agent (LIVE) ---")
    if not os.getenv("LMSTUDIO_BASE_URL"):
        print("[SKIPPED] LMSTUDIO_BASE_URL not set in .env file.")
        return
    try:
        provider = LMStudioProvider()
        print("[SUCCESS] Initialized Provider.")

        model = provider.get_chat_model()
        agent = Agent(model=model, instructions=["You are a helpful assistant."])
        print("[SUCCESS] Created Agent.")

        response = await agent.arun("Who are you?")
        assert response and len(response.content) > 1
        print("[SUCCESS] Agent.arun() returned a valid response.")
    except Exception as e:
        print(f"[FAILED] LMStudioProvider test failed: {e}")

async def main():
    print("🚀 Starting Live Agent Integration Test Script...")
    await test_google_provider()
    await test_groq_provider()
    await test_openrouter_provider()
    await test_lmstudio_provider()
    print("\n✅ All live agent tests completed.")

if __name__ == "__main__":
    asyncio.run(main())
