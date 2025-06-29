import os
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL_ID = "openai/gpt-4o-mini"
API_KEY = os.getenv("OPENROUTER_API_KEY")

PROMPTS_DIR = "prompts"