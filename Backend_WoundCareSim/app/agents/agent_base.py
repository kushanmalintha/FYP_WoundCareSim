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
    Uses Chat Completions with JSON Mode for reliable structured output.
    """

    def __init__(self):
        # Initialize Async Client
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        self.model = OPENAI_CHAT_MODEL

    async def run(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> str:
        """
        Executes an OpenAI Chat Completion call with JSON Mode enforced.
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"}, 
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
            )

            # Extract content directly
            output_text = response.choices[0].message.content

            if not output_text:
                raise ValueError("OpenAI returned empty content.")

            return output_text

        except Exception as e:
            logger.error(f"LLM Call Failed: {e}")
            # Return an empty JSON object as a fallback string to prevent crashes
            return "{}"
