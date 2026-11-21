import os
import json
import hashlib
import logging
import requests
import firebase_admin

from bs4 import BeautifulSoup
from firebase_admin import credentials, firestore

logging.basicConfig(level=logging.INFO)

UPSC_URL = "https://upsc.gov.in/advertisements/"
APPLY_URL = "https://upsconline.nic.in/"

def connect_firebase():
    secret = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")

    if not secret:
        raise ValueError("Firebase secret is missing")

    account = json.loads(secret)

    if not firebase_admin._apps:
        cred = credentials.Certificate(account)
        firebase_admin.initialize_app(cred)

    return firestore.client()


def fetch_upsc_jobs(db):
    headers = {
        "User-Agent": "Mozilla/5.0 SheCareerJobUpdater/1.0"
    }

    response = requests.get(
        UPSC_URL,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    count = 0

    for row in soup.find_all("tr"):
        text = " ".join(row.stripped_strings)

        if "Advertisement" not in text:
            continue

        notification_url = None
        application_url = APPLY_URL

        for link in row.find_all("a", href=True):
            href = link["href"].strip()
            label = link.get_text(" ", strip=True).lower()

            if href.startswith("/"):
                href = "https://upsc.gov.in" + href

            elif href.startswith("//"):
                href = "https:" + href

            if ".pdf" in href.lower():
                notification_url = href

            if "apply" in label:
                application_url = href

        if not notification_url:
            continue

        job_id = hashlib.sha256(
            notification_url.encode()
        ).hexdigest()[:24]

        db.collection("job_review_queue").document(job_id).set({
            "title": text[:200],
            "department": "Union Public Service Commission",
            "category": "UPSC",
            "location": "All India",
            "officialUrl": UPSC_URL,
            "notification": notification_url,
            "applicationUrl": application_url,
            "source": "Official UPSC Website",
            "status": "pending_review",
            "description": (
                "Official UPSC advertisement detected. "
                "Verify post names, vacancies, eligibility "
                "and application deadline from the notification."
            ),
            "sourceVerified": True
        }, merge=True)

        count += 1

    logging.info("UPSC advertisements detected: %s", count)


def main():
    db = connect_firebase()

    fetch_upsc_jobs(db)

    logging.info("UPSC automatic checking completed.")


if __name__ == "__main__":
    main()
