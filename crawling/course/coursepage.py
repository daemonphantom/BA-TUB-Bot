import os
import json
import re
import requests
from urllib.parse import unquote, urlparse
from datetime import datetime
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from ..utils import get_logger

logger = get_logger(__name__)

def crawl(driver, output_path):
    """
    Crawl the visible text content from each section of a TU Berlin course page.
    """
    logger.info("📘 Crawling course sections and text content")

    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CLASS_NAME, "course-section"))
    )
    soup = BeautifulSoup(driver.page_source, "html.parser")

    raw_data = {}
    image_map = {}
    sections = soup.find_all("li", class_=["section", "course-section", "main", "clearfix"])

    for section in sections:
        section_name = section.get("data-sectionname", "").strip()
        if not section_name:
            continue

        # Look inside this section for its content div
        content_div = section.find("div", class_=["content", "course-content-item-content"])
        if content_div:
            # Remove all Moodle activity blocks before extracting text
            for activity in content_div.select("li.activity"):
                modtype = activity.get("class", [])
                if any(cls.startswith("modtype_") and cls not in ["modtype_label"] for cls in modtype):
                    activity.decompose()

            for table in content_div.find_all("table"):
                table_data = extract_table(table)
                if table_data:
                    raw_data[section_name + " (table)"] = table_data
                    table.decompose()

            # Extract and download images
            img_tags = content_div.find_all("img")
            image_map[section_name] = []
            for i, img in enumerate(img_tags, 1):
                src = img.get("src")
                alt = img.get("alt", "")
                if src and "pluginfile.php" in src:
                    image_dir = os.path.join(os.path.dirname(output_path), "coursepage", "images", section_name.replace(" ", "_"))
                    downloaded = download_image(src, image_dir, f"{section_name}_{i}", driver)
                    if downloaded:
                        local_path = downloaded
                        image_map[section_name].append({"src": src, "alt": alt, "local": local_path})
                        img.replace_with(f"(image: {os.path.basename(local_path)})")

            for a in content_div.find_all("a"):
                text = a.get_text()
                href = a.get("href")
                if href:
                    a.replace_with(f"{text} ({href})")
            # Now extract clean content
            content_text = clean_course_text(content_div.get_text(separator=' ', strip=True))
            raw_data[section_name] = content_text
            logger.debug(f"✔️ Section '{section_name}' scraped")

    if raw_data:
        structured_data = transform_course_data(raw_data, driver.current_url)
        for section, images in image_map.items():
            if section in structured_data:
                structured_data[section]["images"] = images
        logger.info(f"✅ Finished crawling. Extracted {len(structured_data)} sections.")
        return structured_data
    else:
        logger.warning("⚠️ No section data found.")
        return {}

def extract_table(table):
    rows = table.find_all("tr")
    if not rows:
        return None

    headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
    data = []

    for row in rows[1:]:
        cells = row.find_all("td")
        if not cells:
            continue

        row_data = {}
        for i in range(min(len(headers), len(cells))):
            value = cells[i].get_text(" ", strip=True)
            row_data[headers[i].strip().title()] = value.strip()

        data.append(row_data)

    return data

def clean_course_text(text: str) -> str:
    # 1. Remove "Aktivität XYZ auswählen" patterns
    text = re.sub(r"Aktivität\s.+?\s+auswählen", "", text)

    # 2. Remove repeated activity titles like "XYZ XYZ"
    text = re.sub(r"\b(\w.+?)\s+\1\b", r"\1", text)

    # 3. Decode mailto garbage links (optional)
    text = re.sub(r"mailto:([^\s)]+)", lambda m: unquote(m.group(1)), text)

    # 4. Remove any remaining Moodle junk like isolated labels
    text = re.sub(r"\b(Video|Datei|Aufgabe|Forum|Textseite|Link/URL|Befragung|Gruppenwahl)\b", "", text)

    # 5. Clean up multiple spaces and punctuation spacing
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([.,:;])", r"\1", text)

    return text.strip()

def transform_course_data(course_data: dict, source_url: str) -> dict:
    transformed = {}

    for section, content in course_data.items():
        is_table = section.endswith(" (table)")
        section_name = section.replace(" (table)", "")

        if section_name not in transformed:
            transformed[section_name] = {
                "text": "",
                "table": [],
                "links": [],
                "metadata": {
                    "incomplete": False,
                    "source": source_url,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }

        if is_table:
            table_cleaned = []
            for row in content:
                cleaned_row = {k.strip().title(): v.strip() for k, v in row.items()}
                table_cleaned.append(cleaned_row)
            transformed[section_name]["table"] = table_cleaned

            if all(not any(cell.strip() for cell in row.values()) for row in table_cleaned):
                transformed[section_name]["metadata"]["incomplete"] = True
        else:
            links = []
            def clean_links(match):
                text, link = match.group(1), match.group(2)
                if text != link:
                    links.append({"text": text, "url": link})
                return f"{text} ({link})"

            clean_text = re.sub(r"([^\s()]+) \((https?://[^\s)]+)\)", clean_links, content)
            urls = re.findall(r"https?://[^\s)]+", clean_text)
            for url in urls:
                if not any(l["url"] == url for l in links):
                    links.append({"text": url, "url": url})

            transformed[section_name]["text"] = clean_text.strip()
            transformed[section_name]["links"] = links

            if not clean_text.strip() or "TBD" in clean_text or "folgt" in clean_text:
                transformed[section_name]["metadata"]["incomplete"] = True

    return transformed

def download_image(url, save_dir, identifier, driver=None):
    os.makedirs(save_dir, exist_ok=True)
    session = requests.Session()

    if driver:
        cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
        session.cookies.update(cookies)

    try:
        parsed_url = urlparse(url)
        ext = os.path.splitext(parsed_url.path)[1].split("?")[0]
        ext = ext if ext.lower() in ['.png', '.jpg', '.jpeg', '.gif'] else '.bin'

        filename = f"{identifier}{ext}"
        filepath = os.path.join(save_dir, filename)

        if not os.path.exists(filepath):
            response = session.get(url, stream=True, timeout=10)
            content_type = response.headers.get("Content-Type", "")
            if response.status_code == 200 and "image" in content_type:
                with open(filepath, "wb") as f:
                    for chunk in response.iter_content(1024):
                        f.write(chunk)
                return filepath
            else:
                logger.warning(f"⚠️ Skipped non-image or failed download: {url} ({content_type})")
                return None
        else:
            return filepath

    except Exception as e:
        logger.warning(f"⚠️ Error downloading image: {url} - {e}")
        return None
