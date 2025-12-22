from pathlib import Path
from openai import OpenAI

from app.core.config import OPENAI_API_KEY, VECTOR_STORE_ID

client = OpenAI(api_key=OPENAI_API_KEY)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def upload_file_to_vector_store(file_path: Path):
    print(f"Uploading: {file_path.name}")

    # Step 1: Upload file
    with open(file_path, "rb") as f:
        uploaded_file = client.files.create(
            file=f,
            purpose="assistants"
        )

    file_id = uploaded_file.id
    print(f"File uploaded. file_id={file_id}")

    # Step 2: Attach to vector store
    client.vector_stores.files.create(
        vector_store_id=VECTOR_STORE_ID,
        file_id=file_id
    )

    print(f"Attached {file_path.name} to vector store.\n")


if __name__ == "__main__":
    for file in DATA_DIR.glob("*.txt"):
        upload_file_to_vector_store(file)

    print("All files uploaded successfully.")
