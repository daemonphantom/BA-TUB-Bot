import os
import json
import requests
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from urllib.parse import urlparse
from .utils.utils import download_image, get_logger, get_course_id_from_url

logger = get_logger(__name__)

def crawl(driver, output_path):
    """
    Download images from activity grids (excluding inline section images).
    Images are resolved from linked resources (e.g. mod/resource/view.php).
    """
    course_id = get_course_id_from_url(driver.current_url)
    logger.info(f"📸 Crawling external images for course {course_id}")

    image_dir = os.path.join(os.path.dirname(output_path), "images")
    os.makedirs(image_dir, exist_ok=True)

    # Step 1: Find activity grids with image icons
    activity_grids = driver.find_elements(By.CSS_SELECTOR, ".activity-grid:has(img[src*='/f/image?'])")
    logger.info(f"Found {len(activity_grids)} image-related activity grids.")

    selenium_cookies = driver.get_cookies()
    cookies = {c['name']: c['value'] for c in selenium_cookies}
    headers = {"User-Agent": driver.execute_script("return navigator.userAgent;")}

    image_entries = []

    for idx, grid in enumerate(activity_grids, 1):
        try:
            a_tag = grid.find_element(By.CSS_SELECTOR, "a[href*='/mod/resource/view.php']")
            moodle_url = a_tag.get_attribute("href")
            title = a_tag.text.strip()

            logger.debug(f"📥 Fetching resource page: {moodle_url}")
            response = requests.get(moodle_url, headers=headers, cookies=cookies, timeout=10)
            if response.status_code != 200:
                logger.warning(f"⚠️ Failed to fetch {moodle_url} (status: {response.status_code})")
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            img_tag = soup.select_one("div.resourceimg img, .resourcecontent img")
            if not img_tag:
                logger.warning(f"⚠️ No image found in resource page: {moodle_url}")
                continue

            img_url = img_tag.get("src")
            if not img_url or "pluginfile.php" not in img_url:
                logger.warning(f"⚠️ Unrecognized or missing image URL in: {moodle_url}")
                continue

            filename = f"{course_id}_{idx}_resource_image"
            saved_path = download_image(img_url, image_dir, filename, driver)

            if saved_path:
                logger.info(f"✅ Downloaded image: {saved_path}")
                image_entries.append({
                    "chunk_type": "image",
                    "title": title,
                    "moodle_url": moodle_url,
                    "image_url": img_url,
                    "saved_filename": os.path.basename(saved_path)
                })

        except Exception as e:
            logger.warning(f"⚠️ Failed to extract or download image: {e}")
            continue

    # Save metadata
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(image_entries, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ Saved metadata for {len(image_entries)} images to {output_path}")
    return image_entries
