import os
import json
import hashlib
import logging
import requests
import firebase_admin

from bs4 import BeautifulSoup
from urllib.parse import urljoin
from firebase_admin import credentials, firestore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

SOURCES = [
    {
        "name": "UPSC",
        "url": "https://upsc.gov.in/advertisements/",
        "department": "Union Public Service Commission",
        "category": "UPSC",
        "location": "All India",
        "official_url": "https://upsc.gov.in/",
        "apply_url": "https://upsconline.nic.in/",
        "keywords": ["advertisement", "recruitment", "vacancy"]
    },
    {
        "name": "MPSC",
        "url": "https://mpsc.gov.in/adv_notification/8",
        "department": "Maharashtra Public Service Commission",
        "category": "MPSC",
        "location": "Maharashtra",
        "official_url": "https://mpsc.gov.in/",
        "apply_url": "https://mpsconline.gov.in/",
        "keywords": ["advertisement", "recruitment", "जाहिरात", "भरती"]
    },
    {
        "name": "SSC",
        "url": "https://ssc.gov.in/home/notice-board",
        "department": "Staff Selection Commission",
        "category": "SSC",
        "location": "All India",
        "official_url": "https://ssc.gov.in/",
        "apply_url": "https://ssc.gov.in/",
        "keywords": [
            "recruitment",
            "examination",
            "notice",
            "combined graduate",
            "combined higher secondary",
            "constable",
            "junior engineer",
            "stenographer"
        ]
    }
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SheCareerJobUpdater/1.0)"
}

def connect_firebase():
    secret = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")

    if not secret:
        raise ValueError("Firebase secret is missing")

    account = json.loads(secret)

    if not firebase_admin._apps:
        cred = credentials.Certificate(account)
        firebase_admin.initialize_app(cred)

    return firestore.client()


def make_job_id(url):
    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()[:24]


def fetch_source(db, source):

    logging.info("Checking %s: %s", source["name"], source["url"])

    try:
        response = requests.get(
            source["url"],
            headers=HEADERS,
            timeout=40
        )

        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        count = 0

        for link in soup.find_all("a", href=True):

            label = link.get_text(" ", strip=True)

            parent_text = link.parent.get_text(
                " ",
                strip=True
            ) if link.parent else ""

            title = " ".join(
                f"{label} {parent_text}".split()
            )

            href = urljoin(source["url"], link["href"].strip())

            if not href.lower().split("?")[0].endswith(".pdf"):
                continue

            searchable_text = title.lower()

            if not any(
                keyword.lower() in searchable_text
                for keyword in source["keywords"]
            ):
                continue

            if len(title) < 5:
                continue

            job_id = make_job_id(href)

            db.collection("job_review_queue").document(
                job_id
            ).set(
                {
                    "title": title[:300],
                    "department": source["department"],
                    "category": source["category"],
                    "location": source["location"],
                    "officialUrl": source["official_url"],
                    "notification": href,
                    "applicationUrl": source["apply_url"],
                    "source": "Official " + source["name"] + " Website",
                    "sourceName": source["name"],
                    "status": "pending_review",
                    "description": (
                        "Official website PDF detected. "
                        "Admin must verify the recruitment details, "
                        "vacancies, eligibility and application dates "
                        "from the official notification before publishing."
                    ),
                    "sourceVerified": True
                },
                merge=True
            )

            count += 1

        logging.info(
            "%s: %s matching PDF links detected",
            source["name"],
            count
        )

    except requests.RequestException as error:
        logging.error(
            "%s website request failed: %s",
            source["name"],
            error
        )

    except Exception:
        logging.exception(
            "%s processing failed",
            source["name"]
        )


def main():

    db = connect_firebase()

    for source in SOURCES:
        fetch_source(db, source)

    logging.info("SheCareer automatic checking completed.")


if __name__ == "__main__":
    main()
