from app.utils.firebase_client import get_firestore_client

db = get_firestore_client()

print("Firestore connected:", db is not None)


# //tests/test_firestore.py

