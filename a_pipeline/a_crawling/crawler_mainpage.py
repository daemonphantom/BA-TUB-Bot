import os
import json
import re
import requests
from urllib.parse import unquote, urlparse
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .utils.utils import *

logger = get_logger(__name__)
BASE_URL = "https://isis.tu-berlin.de/"

def crawl(driver, output_path):
    logger.info("📘 Crawling course sections and text content")

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CLASS_NAME, "course-section"))
    )

    sections = {}

    for section in driver.find_elements(By.CSS_SELECTOR, "li.section.course-section.main.clearfix"):
        try:
            section_name = section.get_attribute("data-sectionname") or "Untitled"

            content_div = section.find_element(By.CSS_SELECTOR, "div.content.course-content-item-content")
            soup = BeautifulSoup(content_div.get_attribute("outerHTML"), "html.parser")

            # 🔥 Remove non-label Moodle activities
            for activity in soup.select("li.activity"):
                modtype = activity.get("class", [])
                if any(cls.startswith("modtype_") and cls not in ["modtype_label"] for cls in modtype):
                    activity.decompose()

            extracted_links = []
            table_data = []

            # 🔥 Annotate font colors + collect
            colors = extract_colors_from_soup(soup)

            # 🔥 Extract & remove tables
            for table in soup.find_all("table"):
                parsed = extract_table(table)
                if parsed:
                    table_data = parsed
                table.decompose()

            # 🔥 Download images
            for i, img in enumerate(soup.find_all("img"), 1):
                src = img.get("src")
                if src and "pluginfile.php" in src:
                    image_dir = os.path.join(os.path.dirname(output_path), "images", section_name.replace(" ", "_"))
                    slug_name = slugify(section_name)
                    downloaded = download_image(src, image_dir, f"{slug_name}_{i}", driver)
                    if downloaded:
                        img.replace_with(f"(image: {os.path.basename(downloaded)})")


            # 🔥 Final text cleanup
            content = clean_course_text(soup.get_text(separator=" ", strip=True))

            # 🔥 Replace <a> with markdown + collect links
            for a in soup.find_all("a", href=True):
                text = a.get_text(separator=" ", strip=True)
                href = unquote(a["href"])
                if not text:
                    text = href
                extracted_links.append({"text": text, "url": href})
                a.replace_with(f"[{text}]({href})")

            sections[section_name] = {
                "text": content.strip(),
                "links": extracted_links,
                "table": table_data,
                "colors": colors,
                "metadata": {
                    "incomplete": False,
                    "source": driver.current_url,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }

        except Exception as e:
            logger.warning(f"⚠️ Failed to process section: {e}")

    if sections:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        structured = transform_course_data(sections)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(structured, f, ensure_ascii=False, indent=2)
        logger.info(f"✅ Finished crawling. Saved to {output_path}")
        return structured
    else:
        logger.warning("⚠️ No section data found.")
        return None
