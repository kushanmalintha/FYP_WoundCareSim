import logging
from openai import AsyncOpenAI  # Use AsyncOpenAI for async/await
from app.core.config import (
    OPENAI_API_KEY,
    VECTOR_STORE_ID,
    OPENAI_CHAT_MODEL,
)

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not configured")

if not VECTOR_STORE_ID:
    raise RuntimeError("VECTOR_STORE_ID not configured")

# Initialize Async Client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def retrieve_with_rag(
    query: str,
    scenario_id: str,
    system_instruction: str = "You are a helpful assistant."
):
    """
    Perform RAG using the stateless OpenAI Responses API.
    """
    try:
        # The simplified Responses API call
        response = await client.responses.create(
            model=OPENAI_CHAT_MODEL,
            
            # 1. Vector Store ID goes INSIDE the tool definition here
            tools=[{
                "type": "file_search",
                "vector_store_ids": [VECTOR_STORE_ID]
            }],
            
            # 2. 'input' can handle a list of messages (conversation history)
            input=[
                {
                    "role": "system",
                    "content": (
                        f"{system_instruction}\n"
                        f"CONSTRAINT: Use only information relevant to scenario_id={scenario_id}."
                    )
                },
                {
                    "role": "user",
                    "content": query
                }
            ]
        )

        # Accessing the text directly
        return {
            "text": response.output_text,  # The new API exposes this directly
            "raw_response": response
        }

    except Exception as e:
        logging.error(f"RAG Retrieval failed: {e}")
        raise e
