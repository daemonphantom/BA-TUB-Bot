import os
import json
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from .utils.utils import get_logger, get_course_id_from_url

logger = get_logger(__name__)

def resolve_target_url(moodle_url, cookies, headers):
    """
    Try to resolve the actual target URL of a Moodle link (view.php?id=...)
    without browser interaction.
    """
    try:
        # 1. Try HEAD to check for redirect
        head_response = requests.head(moodle_url, headers=headers, cookies=cookies, allow_redirects=False, timeout=8)
        if 'Location' in head_response.headers:
            return head_response.headers['Location']

        # 2. Fallback to GET and parse HTML for workaround
        response = requests.get(moodle_url, headers=headers, cookies=cookies, timeout=10)
        if response.status_code != 200:
            logger.warning(f"⚠️ Failed to GET {moodle_url} (status: {response.status_code})")
            return moodle_url

        soup = BeautifulSoup(response.text, "html.parser")

        # Look for urlworkaround div
        workaround = soup.find("div", class_="urlworkaround")
        if workaround:
            link = workaround.find("a", href=True)
            if link:
                return link["href"]

        # Optional: check for <meta http-equiv="refresh">
        meta = soup.find("meta", attrs={"http-equiv": "refresh"})
        if meta and "url=" in meta.get("content", ""):
            return meta["content"].split("url=")[-1].strip()

        return moodle_url

    except Exception as e:
        logger.warning(f"⚠️ Exception while resolving {moodle_url}: {e}")
        return moodle_url


def crawl(driver, output_path):
    """
    Crawl and extract all external links from activity grids with the URL icon.

    Each entry includes:
      - title (e.g. "Zoom-Meeting")
      - description (optional short explanation under the title)
      - target_url (actual destination, resolved from Moodle wrapper)
      - moodle_url (ISIS view.php wrapper)

    Results are saved to output_path as JSON.
    """
    course_id = get_course_id_from_url(driver.current_url)

    # Step 1: Find activity grids with URL icons
    activity_grids = driver.find_elements(By.CSS_SELECTOR, ".activity-grid:has([src*='/url/'])")
    logger.info(f"Found {len(activity_grids)} URL activity grids.")

    # Step 2: Extract cookies and headers for authenticated requests
    selenium_cookies = driver.get_cookies()
    cookies = {c['name']: c['value'] for c in selenium_cookies}
    headers = {"User-Agent": driver.execute_script("return navigator.userAgent;")}

    link_entries = []

    for grid in activity_grids:
        try:
            a_tag = grid.find_element(By.CSS_SELECTOR, "a[href*='/mod/url/view.php']")
            moodle_url = a_tag.get_attribute("href")

            # Clean title by removing accesshide content
            try:
                title_span = a_tag.find_element(By.CSS_SELECTOR, ".instancename")
                title = title_span.text.replace("Link/URL", "").strip()
            except:
                title = a_tag.text.strip()


            # Extract optional description if present
            try:
                desc_elem = grid.find_element(By.CSS_SELECTOR, ".activity-description")
                description = desc_elem.text.strip()
            except:
                description = ""

            actual_url = resolve_target_url(moodle_url, cookies, headers)

            logger.info(f"🔗 Found link -> {title} -> {actual_url}")

            link_entries.append({
                "chunk_type": "external_link",
                "title": title,
                "description": description,
                "target_url": actual_url,
                "moodle_url": moodle_url
            })

        except Exception as e:
            logger.warning(f"⚠️ Failed to extract link from activity grid: {e}")
            continue

    # Save output
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(link_entries, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ Saved {len(link_entries)} external links to {output_path}")
    return link_entries
