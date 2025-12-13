import os
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Load .env variables
load_dotenv()


# Environment variable name (KEEP SAME STYLE AS BEFORE)
FIREBASE_SA = os.getenv("FIREBASE_SERVICE_ACCOUNT")


if not FIREBASE_SA:
    raise RuntimeError(
        "FIREBASE_SERVICE_ACCOUNT env var not set (path to service account JSON)"
    )

# Initialize Firebase app only once
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_SA)
    firebase_admin.initialize_app(cred)

# Firestore client
db = firestore.client()

# --------------------------------------------------
# Core helper functions (simple + explicit)
# --------------------------------------------------

def get_firestore_client():
    """
    Returns Firestore client (singleton)
    """
    return db


def set_document(collection: str, doc_id: str, data: dict):
    """
    Create or overwrite a document
    """
    db.collection(collection).document(doc_id).set(data)


def update_document(collection: str, doc_id: str, data: dict):
    """
    Update an existing document
    """
    db.collection(collection).document(doc_id).update(data)


def get_document(collection: str, doc_id: str):
    """
    Fetch a single document
    """
    doc = db.collection(collection).document(doc_id).get()
    return doc.to_dict() if doc.exists else None


def delete_document(collection: str, doc_id: str):
    """
    Delete a document
    """
    db.collection(collection).document(doc_id).delete()


def get_collection(collection: str):
    """
    Fetch all documents from a collection
    """
    docs = db.collection(collection).stream()
    return [{**doc.to_dict(), "id": doc.id} for doc in docs]


# --------------------------------------------------
# Domain-specific helpers (Week-3 ready)
# --------------------------------------------------

def create_scenario_metadata(scenario_id: str, payload: dict):
    db.collection("scenarios").document(scenario_id).set(payload)


def get_scenario_metadata(scenario_id: str):
    doc = db.collection("scenarios").document(scenario_id).get()
    return doc.to_dict() if doc.exists else None


def log_session_event(session_id: str, event: dict):
    db.collection("sessions") \
      .document(session_id) \
      .collection("events") \
      .add(event)
