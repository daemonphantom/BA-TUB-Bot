import os
import json
import time
import requests
import re
from datetime import datetime
from urllib.parse import urljoin, urlparse, unquote
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .utils.utils import *

logger = get_logger(__name__)
BASE_URL = "https://isis.tu-berlin.de/"



def crawl(driver, output_path):

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CLASS_NAME, "course-section"))
    )

    subpages_data = {}

    # Filter only activity-grids that include /page/
    activity_grids = driver.find_elements(
        By.CSS_SELECTOR, ".activity-grid:has(img[src*='/page/'])"
    )

    subpage_links = []
    for grid in activity_grids:
        try:
            a_tag = grid.find_element(By.CSS_SELECTOR, ".activityname a")
            href = a_tag.get_attribute("href")
            title = a_tag.get_attribute("innerText").replace("Textseite", "").strip()
            if href and title:
                subpage_links.append((href, title))
        except Exception as e:
            logger.debug(f"⚠️ Could not extract link from grid: {e}")

    logger.info(f"Collected {len(subpage_links)} subpage links.")

    for href, title in subpage_links:
        try:
            logger.debug(f"📥 Opening subpage: {title} ({href})")
            driver.get(href)

            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "box"))
            )

            soup = BeautifulSoup(driver.page_source, "html.parser")
            box = soup.find("div", class_="box py-3 generalbox center clearfix")
            if not box:
                continue

            # Extract tables first
            table_data = []
            for table in box.find_all("table"):
                parsed = extract_table(table)
                if parsed:
                    table_data = parsed
                table.decompose()

            # Annotate font colors + collect
            colors = extract_colors_from_soup(soup)

            # Replace image tags
            for i, img in enumerate(box.find_all("img"), 1):
                src = img.get("src")
                if src and "pluginfile.php" in src:
                    image_dir = os.path.join(os.path.dirname(output_path), "subpages", "images", title.replace(" ", "_"))
                    img_filename = os.path.basename(urlparse(src).path)
                    img_name = f"{title}_{i}_{img_filename.split('.')[0]}"  # makes it unique
                    downloaded = download_image(src, image_dir, img_name, driver)
                    if downloaded:
                        img.replace_with(f"(image: {os.path.basename(downloaded)})")

            # Replace links
            extracted_links = []

            for i, a in enumerate(box.find_all("a", href=True)):
                text = a.get_text(separator=" ", strip=True)  # More robust
                href_link = a["href"]

                if not text:
                    text = href_link  # fallback if link text is truly empty

                extracted_links.append({"text": text, "url": href_link})

                # Replace the <a> in HTML to keep the text for 'content'
                a.replace_with(f"{text} ({href_link})")

            content = clean_course_text(box.get_text(separator=" ", strip=True))

            subpages_data = {
                "chunk_type": "subpage",
                "title": title,
                "text": content.strip(),
                "table": table_data,
                "links": extracted_links,
                "colors": colors,
                "metadata": {
                    "incomplete": False,
                    "source": href,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }

        except Exception as e:
            logger.warning(f"⚠️ Failed to crawl {href}: {e}")

    if subpages_data:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        structured = transform_course_data(subpages_data)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(structured, f, ensure_ascii=False, indent=2)
        return structured
    else:
        return None



