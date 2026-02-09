import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
VECTOR_STORE_ID = os.getenv("VECTOR_STORE_ID")
EMBEDDING_MODEL = os.getenv("OPENAI_EMBED_MODEL")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
