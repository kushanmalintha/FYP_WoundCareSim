from abc import ABC
import logging
from openai import AsyncOpenAI

from app.core.config import (
    OPENAI_API_KEY,
    OPENAI_CHAT_MODEL,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """
    Base class for all evaluator agents.
    Uses the 'Responses API' (client.responses.create).
    """

    def __init__(self):
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_CHAT_MODEL

    async def run(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """
        Executes an OpenAI Responses API call and safely extracts text.
        """
        try:
            response = await self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                temperature=temperature,
            )

            # --- PARSING LOGIC FIX ---
            output_text = ""

            # The Responses API returns a list of output items
            if hasattr(response, 'output'):
                for item in response.output:
                    # We are looking for items of type 'message'
                    if getattr(item, 'type', None) == "message":
                        if hasattr(item, 'content'):
                            for content_part in item.content:
                                # CHECK TYPE: It is often "output_text", not just "text"
                                c_type = getattr(content_part, 'type', "")
                                
                                if c_type in ["text", "output_text"]:
                                    text_val = getattr(content_part, 'text', "")
                                    if text_val:
                                        output_text += text_val

            output_text = output_text.strip()

            if not output_text:
                # Debugging help: print what we actually got if empty
                logger.error(f"Raw Response Output: {response.output}")
                raise ValueError("OpenAI returned empty content after parsing.")

            return output_text

        except Exception as e:
            logger.error(f"LLM Responses API Call Failed: {e}")
            # Return empty JSON to prevent crash, but log the error
            return "{}"
