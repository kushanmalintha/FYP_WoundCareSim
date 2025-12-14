from openai import OpenAI

from app.core.config import (
    OPENAI_API_KEY,
    VECTOR_STORE_ID,
    OPENAI_CHAT_MODEL,
)

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not configured")

if not VECTOR_STORE_ID:
    raise RuntimeError("VECTOR_STORE_ID not configured")

client = OpenAI(api_key=OPENAI_API_KEY)


async def retrieve_with_rag(
    query: str,
    scenario_id: str,
    system_instruction: str = ""
):
    """
    Perform Retrieval-Augmented Generation using OpenAI Responses API
    and managed Vector Store via file_search.
    """

    response = await client.responses.create(
        model=OPENAI_CHAT_MODEL,
        tools=[{"type": "file_search"}],
        vector_store_ids=[VECTOR_STORE_ID],
        input=[
            {
                "role": "system",
                "content": (
                    system_instruction +
                    f"\nUse only information relevant to scenario_id={scenario_id}."
                )
            },
            {
                "role": "user",
                "content": query
            }
        ],
    )

    return {
        "text": response.output_text,
        "raw_response": response
    }
