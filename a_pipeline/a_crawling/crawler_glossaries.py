import os, re, json, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .utils.utils import slugify, get_logger

logger = get_logger(__name__)
BASE_URL = "https://isis.tu-berlin.de"


# ──────────────────────────────
# 1. index page  (…/mod/glossary/index.php?id=<course>)
# ──────────────────────────────
def get_glossaries_on_course_page(driver, course_id):
    index_url = f"{BASE_URL}/mod/glossary/index.php?id={course_id}"
    driver.get(index_url)

    try:
        WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.generaltable"))
        )
    except Exception:
        logger.warning("⚠️  Glossary table not found.")
        return []

    soup = BeautifulSoup(driver.page_source, "html.parser")
    table = soup.find("table", class_="generaltable")
    if not table:
        logger.warning("⚠️  Glossary table missing in soup.")
        return []

    glossaries = []
    for row in table.select("tbody tr"):
        try:
            cells = row.find_all("td")
            link          = cells[1].find("a")                      # ‘Name’ column
            glossary_url  = urljoin(index_url, link.get("href"))
            glossary_id   = parse_qs(urlparse(glossary_url).query).get("id", [""])[0]
            entry_count   = int(cells[2].text.strip())              # ‘Einträge’ column
            glossaries.append({
                "title"       : link.text.strip(),
                "url"         : glossary_url,
                "glossary_id" : glossary_id,
                "entry_count" : entry_count
            })
        except Exception as e:
            logger.warning(f"⚠️  Skipping glossary row: {e}")
            continue
    return glossaries


# ──────────────────────────────
# 2. helper – how many pages does a glossary have?
# ──────────────────────────────
def detect_total_pages(driver):
    """
    Look at the paging bar and return the highest page index (0‑based) + 1.
    If no paging bar, return 1.
    """
    soup = BeautifulSoup(driver.page_source, "html.parser")
    paging = soup.find("div", class_="paging")
    if not paging:
        return 1
    numbers = [int(a.text) for a in paging.select("a") if a.text.isdigit()]
    return max(numbers) if numbers else 1


# ──────────────────────────────
# 3. parse a single glossary page (one URL, may hold ≤ X entries)
# ──────────────────────────────
def parse_glossary_page(html):
    soup = BeautifulSoup(html, "html.parser")
    posts = []

    for table in soup.find_all("table", class_="glossarypost"):
        try:
            # header part
            h4        = table.find("div", class_="concept").find("h4")
            question  = h4.get_text(" ", strip=True)
            date_span = table.find("span", class_="time")
            date_str  = date_span.get_text(" ", strip=True) if date_span else "Unknown"

            # answer part
            answer_td  = table.find("td", class_="entry")
            # convert internal links → "text (URL)"
            for a in answer_td.find_all("a"):
                a.replace_with(f"{a.get_text()} ({a.get('href')})")
            answer     = answer_td.get_text(" ", strip=True)

            posts.append({
                "question" : question,
                "answer"   : answer,
                "edited"   : date_str
            })
        except Exception as e:
            logger.warning(f"⚠️  Error parsing glossary entry: {e}")
            continue
    return posts


# ──────────────────────────────
# 4. crawl one glossary (multi‑page)
# ──────────────────────────────
def crawl_glossary(driver, glossary, save_dir, course_id, index):
    logger.info(f"📖 Glossary: {glossary['title']} ({glossary['entry_count']} Einträge)")
    all_entries = []

    # first page
    driver.get(glossary["url"])
    total_pages = detect_total_pages(driver)

    for p in range(total_pages):
        if p > 0:
            driver.get(f"{glossary['url']}&page={p}")
        try:
            WebDriverWait(driver, 4).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "table.glossarypost"))
            )
        except Exception:
            logger.warning(f"⚠️  No entries found on page {p} of glossary.")
            continue
        page_entries = parse_glossary_page(driver.page_source)
        all_entries.extend(page_entries)

    # save JSON
    safe_name  = slugify(glossary["title"])
    filepath   = os.path.join(save_dir, f"{course_id}_glossary_{index:02d}_{safe_name}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)
    return filepath, len(all_entries)


# ──────────────────────────────
# 5. public entry‑point  (mirrors forum.crawl signature)
# ──────────────────────────────
def crawl(driver, gloss_folder):
    """
    Crawl every glossary in a course and store each as its own JSON file.
    """
    os.makedirs(gloss_folder, exist_ok=True)
    course_id = parse_qs(urlparse(driver.current_url).query).get("id", ["unknown"])[0]
    if course_id in ["unknown", "1"]:
        logger.error("⚠️  Invalid course ID. Aborting glossary crawl.")
        return []

    glossaries = get_glossaries_on_course_page(driver, course_id)
    summary    = []

    for idx, gloss in enumerate(glossaries, start=1):
        save_path, cnt = crawl_glossary(driver, gloss, gloss_folder, course_id, idx)
        summary.append({
            "title"      : gloss["title"],
            "entries"    : cnt,
            "saved_to"   : save_path
        })
    logger.info(f"✅ Saved metadata for {len(summary)} glossaries to {gloss_folder}")
    return summary
