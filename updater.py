import os
import json
import hashlib
import logging
from urllib.parse import urljoin, urlparse

import firebase_admin
from firebase_admin import credentials, firestore
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


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
        "location": "All India"
    },
    {
        "name": "MPSC",
        "url": "https://mpsc.gov.in/adv_notification/8",
        "department": "Maharashtra Public Service Commission",
        "category": "MPSC",
        "location": "Maharashtra"
    },
    {
        "name": "SSC",
        "url": "https://ssc.gov.in/home/notice-board",
        "department": "Staff Selection Commission",
        "category": "SSC",
        "location": "All India"
    }
]

KEYWORDS = [
    "recruitment", "advertisement", "vacancy", "notification",
    "application", "selection post", "constable", "cgl",
    "chsl", "mts", "stenographer", "junior engineer",
    "भरती", "जाहिरात", "पदभरती", "सरळसेवा"
]


def connect_firebase():
    secret = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")

    if not secret:
        raise ValueError("Firebase service account secret is missing.")

    account = json.loads(secret)

    if not firebase_admin._apps:
        cred = credentials.Certificate(account)
        firebase_admin.initialize_app(cred)

    return firestore.client()


def is_pdf_url(url):
    path = urlparse(url).path.lower()
    return path.endswith(".pdf") or ".pdf" in url.lower()


def has_recruitment_keyword(text):
    text = text.lower()
    return any(word in text for word in KEYWORDS)


def save_to_review_queue(db, source, title, notification_url):
    job_id = hashlib.sha256(
        notification_url.encode("utf-8")
    ).hexdigest()[:24]

    db.collection("job_review_queue").document(job_id).set({
        "title": title[:250],
        "department": source["department"],
        "category": source["category"],
        "location": source["location"],
        "notification": notification_url,
        "officialUrl": source["url"],
        "applicationUrl": "",
        "source": source["name"],
        "sourceDomainOfficial": True,
        "status": "pending_review",
        "description": (
            "Official website link detected. "
            "Admin must verify the notification PDF, "
            "post details, vacancies, eligibility and dates "
            "before publishing."
        )
    }, merge=True)


def scan_source(browser, db, source):
    name = source["name"]
    url = source["url"]

    logging.info("Checking %s: %s", name, url)

    page = browser.new_page()
    found = set()
    count = 0

    try:
        response = page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        if response and response.status >= 400:
            logging.warning(
                "%s returned HTTP status %s",
                name,
                response.status
            )

        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeoutError:
            pass

        page.wait_for_timeout(5000)

        links = page.locator("a[href]").evaluate_all("""
            elements => elements.map(a => {
                let parent = a.parentElement;
                let context = "";

                for (let i = 0; i < 3 && parent; i++) {
                    context += " " + (parent.innerText || "");
                    parent = parent.parentElement;
                }

                return {
                    href: a.href,
                    text: a.innerText || a.getAttribute("aria-label") || "",
                    context: context
                };
            })
        """)

        logging.info("%s: %s links found", name, len(links))

        for link in links:
            href = link.get("href", "").strip()
            text = link.get("text", "").strip()
            context = link.get("context", "").strip()

            if not href.startswith("http"):
                continue

            domain = urlparse(href).netloc.lower()

            if not domain.endswith((
                "upsc.gov.in",
                "upsconline.nic.in",
                "mpsc.gov.in",
                "ssc.gov.in"
            )):
                continue

            combined_text = f"{text} {context}"

            pdf_link = is_pdf_url(href)

            relevant = has_recruitment_keyword(combined_text)

            # PDF links are collected only when their surrounding
            # page text appears related to recruitment.
            if not pdf_link or not relevant:
                continue

            if href in found:
                continue

            found.add(href)

            title = " ".join(combined_text.split())
            if not title:
                title = f"{name} official recruitment notification"

            save_to_review_queue(db, source, title, href)
            count += 1

        logging.info(
            "%s: %s matching notification links detected",
            name,
            count
        )

    except Exception as error:
        logging.exception("%s checking failed: %s", name, error)

    finally:
        page.close()


def main():
    db = connect_firebase()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        try:
            for source in SOURCES:
                scan_source(browser, db, source)
        finally:
            browser.close()

    logging.info("SheCareer automatic checking completed.")


if __name__ == "__main__":
    main()
