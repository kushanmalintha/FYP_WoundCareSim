import os
from typing import List
from app.rag.vector_client import VectorClient

ALLOWED_EXTENSIONS = {".pdf", ".txt"}

async def ingest_scenario_documents(
    scenario_id: str,
    file_paths: List[str]
) -> List[str]:
    """
    Uploads scenario reference documents to OpenAI Vector Store.
    Returns list of OpenAI file_ids.
    """

    client = VectorClient()
    uploaded_file_ids = []

    for path in file_paths:
        ext = os.path.splitext(path)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {path}")

        file_id = await client.upload_file(scenario_id, path)
        uploaded_file_ids.append(file_id)

    return uploaded_file_ids


async def delete_scenario_documents(file_ids: List[str]):
    """
    Deletes all vector store documents associated with a scenario.
    """

    client = VectorClient()

    for file_id in file_ids:
        try:
            await client.delete_file(file_id)
        except Exception:
            pass  # safe cleanup
