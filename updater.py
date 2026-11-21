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
        "apply": "https://upsconline.nic.in/",
        "domains": ["upsc.gov.in", "upsconline.nic.in"]
    },
    {
        "name": "MPSC",
        "url": "https://mpsc.gov.in/adv_notification/8",
        "department": "Maharashtra Public Service Commission",
        "category": "MPSC",
        "location": "Maharashtra",
        "apply": "https://mpsc.gov.in/",
        "domains": ["mpsc.gov.in"]
    },
    {
        "name": "SSC",
        "url": "https://ssc.gov.in/home/notice-board",
        "department": "Staff Selection Commission",
        "category": "SSC",
        "location": "All India",
        "apply": "https://ssc.gov.in/",
        "domains": ["ssc.gov.in"]
    }
]

KEYWORDS = [
    "recruitment",
    "advertisement",
    "notification",
    "vacancy",
    "vacancies",
    "application invited",
    "apply online",
    "selection post",
    "combined graduate",
    "combined higher secondary",
    "constable recruitment",
    "junior engineer",
    "stenographer",
    "direct recruitment",
    "भरती",
    "जाहिरात",
    "पदभरती",
    "सरळसेवा"
]

EXCLUDE = [
    "admit card",
    "answer key",
    "result",
    "response sheet",
    "exam city",
    "examination city",
    "marks of candidates",
    "final answer key",
    "score card",
    "exam date",
    "examination schedule"
]


def connect_firebase():
    secret = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")

    if not secret:
        raise ValueError("Firebase service account secret missing")

    account = json.loads(secret)

    if not firebase_admin._apps:
        cred = credentials.Certificate(account)
        firebase_admin.initialize_app(cred)

    return firestore.client()


def official_domain(url, source):
    host = urlparse(url).netloc.lower().split(":")[0]

    return any(
        host == domain or host.endswith("." + domain)
        for domain in source["domains"]
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
        (source["name"] + notification).encode("utf-8")
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
        "detectedAt": firestore.SERVER_TIMESTAMP,
        "description": (
            "Official website notice detected automatically. "
            "This is not yet a verified vacancy. Admin must check "
            "the official notification PDF, vacancy details, "
            "eligibility and application dates before publishing."
        )
    }, merge=True)


def extract_links(page):
    return page.locator("a[href]").evaluate_all("""
        elements => elements.map(a => {
            let context = "";
            let parent = a;

            for (let i = 0; i < 4 && parent; i++) {
                context += " " + (parent.innerText || "");
                parent = parent.parentElement;
            }

            return {
                href: a.href,
                label: a.innerText || "",
                context: context
            };
        })
    """)


def scan_source(browser, db, source):
    name = source["name"]
    page = browser.new_page()
    found = set()
    count = 0

    logging.info("Checking %s: %s", name, source["url"])

    try:
        response = page.goto(
            source["url"],
            wait_until="domcontentloaded",
            timeout=60000
        )

        if response:
            logging.info("%s HTTP status: %s", name, response.status)

        try:
            page.wait_for_load_state(
                "networkidle",
                timeout=15000
            )
        except PlaywrightTimeoutError:
            pass

        page.wait_for_timeout(5000)

        # UPSC advertisement table
        if name == "UPSC":
            rows = page.locator("tr").evaluate_all("""
                rows => rows.map(row => ({
                    text: row.innerText || "",
                    links: Array.from(row.querySelectorAll("a")).map(a => ({
                        label: a.innerText || "",
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
                    label = link["label"].lower().strip()

                    if not href or not official_domain(href, source):
                        continue

                    if "apply" in label:
                        continue

                    if (
                        "view" in label
                        or "pdf" in label
                        or ".pdf" in urlparse(href).path.lower()
                    ):
                        if href not in found:
                            found.add(href)
                            save_job(db, source, title, href)
                            count += 1

        # MPSC and SSC: scan all official links
        links = extract_links(page)

        for link in links:
            href = link["href"].strip()
            label = " ".join(link["label"].split())
            context = " ".join(link["context"].split())

            if not href or href in found:
                continue

            if not official_domain(href, source):
                continue

            combined_text = (label + " " + context).strip()

            if not relevant_title(combined_text):
                continue

            path = urlparse(href).path.lower()
            is_pdf = path.endswith(".pdf")

            is_notice_link = any(
                word in label.lower()
                for word in ["view", "notification", "advertisement", "download"]
            )

            if not is_pdf and not is_notice_link:
                continue

            found.add(href)

            title = label if label else combined_text
            save_job(db, source, title, href)
            count += 1

        logging.info(
            "%s: %s candidate notices detected",
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

    logging.info("SheCareer automatic checking completed")


if __name__ == "__main__":
    main()
