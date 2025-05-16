# feedback.py   (place in crawling/course/)
import os, json, re, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .utils.utils import slugify, get_logger

logger   = get_logger(__name__)
BASE_URL = "https://isis.tu-berlin.de"


# ─────────────────────────────────────────────────────────
# 1.  index page  …/mod/feedback/index.php?id=<course_id>
# ─────────────────────────────────────────────────────────
def list_feedback_activities(driver, course_id):
    index_url = f"{BASE_URL}/mod/feedback/index.php?id={course_id}"
    driver.get(index_url)

    try:
        WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.generaltable"))
        )
    except Exception:
        logger.warning("⚠️  Feedback table not found.")
        return []

    soup  = BeautifulSoup(driver.page_source, "html.parser")
    table = soup.find("table", class_="generaltable")
    if not table:
        return []

    activities = []
    for row in table.select("tbody tr"):
        try:
            link   = row.find_all("td")[1].find("a")              # ‘Name’ column
            title  = link.text.strip()
            url    = link["href"] if link["href"].startswith("http") else urljoin(index_url, link["href"])
            act_id = parse_qs(urlparse(url).query).get("id", [""])[0]
            activities.append({"title": title, "url": url, "id": act_id})
        except Exception as e:
            logger.warning(f"⚠️  Skipping feedback row: {e}")
    return activities


# ─────────────────────────────────────────────────────────
# 2.  helper - grab the “complete” URL from view page
# ─────────────────────────────────────────────────────────
def get_complete_url(driver, view_url):
    driver.get(view_url)
    try:
        WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='complete.php']"))
        )
        a = driver.find_element(By.CSS_SELECTOR, "a[href*='complete.php']")
        return a.get_attribute("href")
    except Exception:
        logger.warning("⚠️  No 'Formular ausfüllen' link on view page.")
        return None


# ─────────────────────────────────────────────────────────
# 3.  parse one page of a feedback form
# ─────────────────────────────────────────────────────────
def parse_feedback_page(html):
    soup  = BeautifulSoup(html, "html.parser")
    items = []

    for wrapper in soup.select("div.feedback_itemlist"):
        try:
            # take the question text from the column‑label block
            q_label  = wrapper.find_previous("div", class_="col-md-3").get_text(" ", strip=True)
            question = re.sub(r"\s*\*?$", "", q_label)            # trim trailing *

            ftype, options = "unknown", []
            if wrapper.select("input[type='radio']"):
                ftype   = "multichoice_radio"
                options = [lab.get_text(" ", strip=True)
                           for lab in wrapper.select("label")
                           if "Nicht gewählt" not in lab.get_text()]
            elif wrapper.select("select"):
                ftype   = "multichoice_select"
                options = [o.get_text(" ", strip=True)
                           for o in wrapper.select("option")
                           if o.get("value") != "0"]
            elif wrapper.select("textarea"):
                ftype   = "textarea"

            items.append({
                "question": question,
                "type"    : ftype,
                "options" : options
            })
        except Exception as e:
            logger.warning(f"⚠️  Error parsing feedback item: {e}")
    return items



def has_next_button(soup):
    """Return True if a 'Nächste Seite' submit button exists on this page."""
    return bool(soup.select_one("input[name='gonextpage']"))


# ─────────────────────────────────────────────────────────
# 4.  crawl a single feedback activity (iterate pages)
# ─────────────────────────────────────────────────────────
def crawl_feedback(driver, activity, save_dir, course_id, idx):
    logger.info(f"📝 Feedback: {activity['title']}")
    complete_url = get_complete_url(driver, activity["url"])
    if not complete_url:
        return None, 0

    page = 0
    entries = []
    # in crawl_feedback()
    while True:
        url = f"{complete_url}&gopage={page}"
        driver.get(url)
        WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "form#feedback_complete_form"))
        )

        soup  = BeautifulSoup(driver.page_source, "html.parser")
        items = parse_feedback_page(driver.page_source)
        if items:
            entries.extend(items)           # ← keep items if any, but do NOT break on empty

        if not has_next_button(soup):       # ← break only when no “Nächste Seite”
            break
        page += 1

    # save JSON
    safe_name = slugify(activity["title"])
    path      = os.path.join(save_dir, f"{course_id}_feedback_{idx:02d}_{safe_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)
    return path, len(entries)


# ─────────────────────────────────────────────────────────
# 5.  public entry‑point
# ─────────────────────────────────────────────────────────
def crawl(driver, fb_folder):
    """
    Crawl every feedback activity in a course.
    """
    os.makedirs(fb_folder, exist_ok=True)
    course_id = parse_qs(urlparse(driver.current_url).query).get("id", ["unknown"])[0]
    if course_id in ["unknown", "1"]:
        logger.error("⚠️  Invalid course ID - aborting feedback crawl.")
        return []

    activities = list_feedback_activities(driver, course_id)
    summary    = []

    for i, act in enumerate(activities, start=1):
        res = crawl_feedback(driver, act, fb_folder, course_id, i)
        if res[0]:
            summary.append({"title": act["title"], "questions": res[1], "saved_to": res[0]})

    logger.info(f"✅ Saved {len(summary)} feedback forms to {fb_folder}")
    return summary
