import os
import json
import logging
import firebase_admin

from firebase_admin import credentials, firestore

logging.basicConfig(level=logging.INFO)

def main():
    secret = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")

    if not secret:
        raise ValueError("Firebase secret is missing!")

    service_account = json.loads(secret)

    if not firebase_admin._apps:
        cred = credentials.Certificate(service_account)
        firebase_admin.initialize_app(cred)

    db = firestore.client()

    logging.info("SheCareer Firebase connection successful!")

    # Only verified jobs from configured official sources
    # will be added in the next step.

    jobs = db.collection("jobs").stream()

    count = sum(1 for _ in jobs)

    logging.info("Existing jobs in Firebase: %s", count)
    logging.info("Automatic updater is ready for official sources.")

if __name__ == "__main__":
    main()
