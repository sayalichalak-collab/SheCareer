import os
import json
import hashlib
import logging
from urllib.parse import urlparse

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
        "location": "All India",
        "apply": "https://upsconline.nic.in/"
    },
    {
        "name": "MPSC",
        "url": "https://mpsc.gov.in/adv_notification/8",
        "department": "Maharashtra Public Service Commission",
        "category": "MPSC",
        "location": "Maharashtra",
        "apply": ""
    },
    {
        "name": "SSC",
        "url": "https://ssc.gov.in/home/notice-board",
        "department": "Staff Selection Commission",
        "category": "SSC",
        "location": "All India",
        "apply": "https://ssc.gov.in/"
    }
]

KEYWORDS = [
    "recruitment", "advertisement", "notification",
    "vacancy", "selection post", "apply online",
    "combined graduate", "combined higher secondary",
    "constable", "stenographer", "junior engineer",
    "भरती", "जाहिरात", "पदभरती", "सरळसेवा"
]

EXCLUDE = [
    "admit card", "answer key", "result",
    "response sheet", "exam city", "examination city",
    "interview schedule", "marks of candidates"
]


def connect_firebase():
    secret = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")

    if not secret:
        raise ValueError("Firebase secret missing")

    account = json.loads(secret)

    if not firebase_admin._apps:
        cred = credentials.Certificate(account)
        firebase_admin.initialize_app(cred)

    return firestore.client()


def official_domain(url, source):
    host = urlparse(url).netloc.lower()

    allowed = {
        "UPSC": ["upsc.gov.in", "upsconline.nic.in"],
        "MPSC": ["mpsc.gov.in"],
        "SSC": ["ssc.gov.in"]
    }

    return any(
        host == domain or host.endswith("." + domain)
        for domain in allowed[source["name"]]
    )


def relevant_title(text):
    text = text.lower()

    if any(word in text for word in EXCLUDE):
        return False

    return any(word in text for word in KEYWORDS)


def save_job(db, source, title, notification):
    if not notification:
        return

    job_id = hashlib.sha256(
        notification.encode("utf-8")
    ).hexdigest()[:24]

    db.collection("job_review_queue").document(job_id).set({
        "title": title[:250],
        "department": source["department"],
        "category": source["category"],
        "location": source["location"],
        "notification": notification,
        "applicationUrl": source["apply"],
        "officialUrl": source["url"],
        "source": source["name"],
        "sourceDomainOfficial": True,
        "status": "pending_review",
        "description": (
            "Official website notice detected. "
            "Admin must verify the complete notification, "
            "vacancies, eligibility and application dates "
            "before publishing."
        )
    }, merge=True)


def scan_source(browser, db, source):
    name = source["name"]
    page = browser.new_page()

    count = 0
    found = set()

    logging.info("Checking %s", name)

    try:
        response = page.goto(
            source["url"],
            wait_until="domcontentloaded",
            timeout=60000
        )

        if response and response.status >= 400:
            logging.warning(
                "%s HTTP status: %s",
                name,
                response.status
            )

        try:
            page.wait_for_load_state(
                "networkidle",
                timeout=15000
            )
        except PlaywrightTimeoutError:
            pass

        page.wait_for_timeout(5000)

        # UPSC: Read advertisement table rows,
        # including View links that may not end in .pdf.
        if name == "UPSC":
            rows = page.locator("tr").evaluate_all("""
                rows => rows.map(row => ({
                    text: row.innerText || "",
                    links: Array.from(row.querySelectorAll("a"))
                        .map(a => ({
                            text: a.innerText || "",
                            href: a.href
                        }))
                }))
            """)

            for row in rows:
                title = " ".join(row["text"].split())

                if "advertisement" not in title.lower():
                    continue

                for link in row["links"]:
                    href = link["href"].strip()
                    label = link["text"].strip().lower()

                    if not href or not official_domain(href, source):
                        continue

                    if "view" in label or "pdf" in href.lower():
                        if href not in found:
                            found.add(href)
                            save_job(db, source, title, href)
                            count += 1

        # MPSC and SSC: Read visible official PDF links.
        links = page.locator("a[href]").evaluate_all("""
            elements => elements.map(a => {
                let parent = a.parentElement;
                let context = a.innerText || "";

                for (let i = 0; i < 3 && parent; i++) {
                    context += " " + (parent.innerText || "");
                    parent = parent.parentElement;
                }

                return {
                    href: a.href,
                    text: context
                };
            })
        """)

        for link in links:
            href = link["href"].strip()
            title = " ".join(link["text"].split())

            if not href or href in found:
                continue

            if not official_domain(href, source):
                continue

            if ".pdf" not in urlparse(href).path.lower():
                continue

            if not relevant_title(title):
                continue

            found.add(href)
            save_job(db, source, title, href)
            count += 1

        logging.info(
            "%s: %s notices detected",
            name,
            count
        )

    except Exception:
        logging.exception("%s scanning failed", name)

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

    logging.info("SheCareer checking completed")


if __name__ == "__main__":
    main()
