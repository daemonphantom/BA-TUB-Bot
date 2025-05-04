import os
import json
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from ..utils import get_logger, get_course_id_from_url

logger = get_logger(__name__)

def download_file_with_cookies(url, filepath, cookies):
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        response = requests.get(url, cookies=cookies, stream=True, timeout=15)
        if response.status_code == 200:
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            return True
        else:
            logger.warning(f"⚠️ Failed to download {url} (status: {response.status_code})")
            return False
    except Exception as e:
        logger.warning(f"⚠️ Exception downloading {url}: {e}")
        return False

def crawl(driver, output_path):
    """
    Crawl archive/folder activity grids with downloadable files (e.g. ZIPs).
    Intercepts actual download triggered by browser via pluginfile.php.
    """
    course_id = get_course_id_from_url(driver.current_url)
    logger.info(f"📦 Extracting archive resources for course {course_id}")

    # Step 1: Find activity grids with archive icons
    activity_grids = driver.find_elements(By.CSS_SELECTOR, ".activity-grid:has([src*='/f/archive'])")
    logger.info(f"Found {len(activity_grids)} archive activity grids.")

    downloaded = []
    cookies = {c['name']: c['value'] for c in driver.get_cookies()}

    for i, grid in enumerate(activity_grids, 1):
        try:
            a_tag = grid.find_element(By.CSS_SELECTOR, "a[href*='/mod/resource/view.php']")
            moodle_url = a_tag.get_attribute("href")
            title = a_tag.text.strip()

            # Clear Selenium Wire request history
            driver.request_interceptor = None
            driver.scopes = ['.*pluginfile\\.php.*']
            driver._client.clear_network_interceptor()
            driver.proxy.clear_interceptor_requests()
            driver.requests.clear()

            driver.get(moodle_url)

            # Wait and find intercepted pluginfile.php request
            matched_request = None
            for req in driver.requests:
                if req.response and "pluginfile.php" in req.url and req.response.status_code == 200:
                    matched_request = req
                    break

            if not matched_request:
                logger.warning(f"⚠️ No downloadable link found on {moodle_url}")
                continue

            url = matched_request.url
            filename = os.path.basename(urlparse(url).path)
            save_dir = os.path.join(os.path.dirname(output_path), "files")
            save_path = os.path.join(save_dir, f"{course_id}_{i:02d}_{filename}")

            if download_file_with_cookies(url, save_path, cookies):
                logger.info(f"✅ Downloaded archive: {save_path}")
                downloaded.append({
                    "title": title,
                    "moodle_url": moodle_url,
                    "download_url": url,
                    "saved_filename": os.path.basename(save_path),
                    "saved_path": save_path
                })

        except Exception as e:
            logger.warning(f"⚠️ Failed to process archive link: {e}")
            continue

    # Save metadata
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(downloaded, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ Saved metadata for {len(downloaded)} archive files to {output_path}")
    return downloaded
