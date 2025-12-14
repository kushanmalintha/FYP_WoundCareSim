from typing import List
from openai import OpenAI

from app.core.config import OPENAI_API_KEY, VECTOR_STORE_ID

class VectorClient:
    """
    Handles ONLY OpenAI Vector Store file management.
    No querying logic lives here.
    """

    def __init__(self):
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY not configured")

        if not VECTOR_STORE_ID:
            raise RuntimeError("VECTOR_STORE_ID not configured")

        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.vector_store_id = VECTOR_STORE_ID

    async def upload_file(self, scenario_id: str, file_path: str) -> str:
        """
        Upload a document to OpenAI and attach it to the vector store.
        OpenAI performs chunking + embedding automatically.
        """

        file_obj = await self.client.files.create(
            file=open(file_path, "rb"),
            purpose="assistants",
            metadata={
                "scenario_id": scenario_id
            }
        )

        await self.client.vector_stores.files.create(
            vector_store_id=self.vector_store_id,
            file_id=file_obj.id
        )

        return file_obj.id

    async def delete_file(self, file_id: str):
        """
        Remove file and its embeddings from the vector store.
        """
        await self.client.vector_stores.files.delete(
            vector_store_id=self.vector_store_id,
            file_id=file_id
        )
