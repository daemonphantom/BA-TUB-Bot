import os, time
import requests
import re
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote
from ..misc import get_logger

logger = get_logger(__name__)

def extract_table(table):
    rows = table.find_all("tr")
    if not rows:
        return None

    headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
    data = []

    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        row_data = {}
        for i in range(min(len(headers), len(cells))):
            cell = cells[i]

            # Farbige Spans annotieren, aber ignoriere schwarz
            for span in cell.find_all("span", style=True):
                style = span.get("style", "")
                if "color" in style:
                    color_match = re.search(r"color:\s*([^;]+)", style)
                    if color_match:
                        color = color_match.group(1).strip().lower()

                        # 🔥 Ignore black shades
                        if color in {"black", "rgb(0, 0, 0)", "#000", "#000000"}:
                            continue

                        text = span.get_text(strip=True)
                        span.replace_with(f"{text} (color: {color})")

            value = cell.get_text(" ", strip=True)
            row_data[headers[i].strip().title()] = value.strip()
        data.append(row_data)

    # Optional forward fill
    safe_to_fill = {"Tag", "Zeit"}
    last_full = {}
    for row in data:
        for key in headers:
            col = key.strip().title()
            if row.get(col):
                last_full[col] = row[col]
            elif col in safe_to_fill:
                row[col] = last_full.get(col, "")

    return data



def clean_course_text(text: str) -> str:
    # 1. Remove "Aktivität XYZ auswählen" patterns
    text = re.sub(r"Aktivität\s.+?\s+auswählen", "", text)

    # 2. Remove repeated activity titles like "XYZ XYZ"
    text = re.sub(r"\b(\w.+?)\s+\1\b", r"\1", text)

    # 3. Decode mailto garbage links (optional)
    text = re.sub(r"mailto:([^\s)]+)", lambda m: unquote(m.group(1)), text)

    # 4. Remove any remaining Moodle junk like isolated labels
    text = re.sub(r"^(?:Video|Datei|Aufgabe|Forum|Textseite|Link/URL|Befragung|Gruppenwahl)\s*$","",text,flags=re.MULTILINE)

    # 5. Clean up multiple spaces and punctuation spacing
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+([.,:;])", r"\1", text)

    return text.strip()


def transform_course_data(course_data: dict, source_url: str = None) -> dict:
    transformed = {}

    for section, content in course_data.items():
        is_table = isinstance(content, dict) and "text" in content
        section_name = section.replace(" (table)", "") if section.endswith(" (table)") else section

        if section_name not in transformed:
            transformed[section_name] = {
                "text": "",
                "table": [],
                "links": [],
                "colors": [],
                "metadata": {
                    "incomplete": False,
                    "source": source_url,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            }

        if is_table:
            text = content.get("text", "").strip()
            table = content.get("table", [])
            links = content.get("links", [])
            colors = content.get("colors", [])
            metadata = content.get("metadata", {})

            transformed[section_name]["text"] = text
            transformed[section_name]["table"] = [
                {k.strip().title(): v.strip() for k, v in row.items()} for row in table
            ]
            transformed[section_name]["links"] = links
            transformed[section_name]["colors"] = colors
            transformed[section_name]["metadata"].update(metadata)

            if not text or "TBD" in text or "folgt" in text:
                transformed[section_name]["metadata"]["incomplete"] = True

            if (
                len(text) < 40
                and all(".mp4" in l["url"] for l in links)
                and len(links) > 5
            ):
                transformed[section_name]["metadata"]["incomplete"] = True
                transformed[section_name]["metadata"]["reason"] = "video-only subpage"

        else:
            links = []

            # legacy fallback if only raw text is given (rare)
            text = content
            transformed[section_name]["text"] = text.strip()
            transformed[section_name]["links"] = links
            transformed[section_name]["metadata"]["source"] = source_url
            transformed[section_name]["metadata"]["timestamp"] = datetime.now(timezone.utc).isoformat()

            if not text.strip() or "TBD" in text or "folgt" in text:
                transformed[section_name]["metadata"]["incomplete"] = True

            if (
                len(text.strip()) < 400
                and all(".mp4" in link["url"] for link in links)
                and len(links) > 5
            ):
                transformed[section_name]["metadata"]["incomplete"] = True
                transformed[section_name]["metadata"]["reason"] = "video-only subpage"

    return transformed



def download_image(url, save_dir, identifier, driver=None):
    os.makedirs(save_dir, exist_ok=True)
    session = requests.Session()
    if driver:
        cookies = {cookie['name']: cookie['value'] for cookie in driver.get_cookies()}
        session.cookies.update(cookies)
    retries=3
    for attempt in range(retries):
        try:
            parsed_url = urlparse(url)
            ext = os.path.splitext(parsed_url.path)[1].split("?")[0]
            ext = ext if ext.lower() in ['.png', '.jpg', '.jpeg', '.gif', '.svg'] else '.bin'
            filename = f"{identifier}{ext}"
            filepath = os.path.join(save_dir, filename)
            logger.info(f"📥 Downloading with cookies: {url}")
            if not os.path.exists(filepath):
                response = session.get(url, stream=True, timeout=25)
                content_type = response.headers.get("Content-Type", "")
                if response.status_code == 200 and "image" in content_type:
                    with open(filepath, "wb") as f:
                        for chunk in response.iter_content(1024):
                            if chunk:
                                f.write(chunk)
                    return filepath
                else:
                    logger.warning(f"⚠️ Ungültiger Content-Type {content_type} für {url}")
                    return None
            return filepath
        except Exception as e:
            logger.warning(f"⚠️ Versuch {attempt+1}/{retries} fehlgeschlagen: {e}")
            time.sleep(1)
    logger.warning(f"❌ Alle Versuche fehlgeschlagen: {url}")
    return None
 

def slugify(name: str) -> str:
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss"
    }
    for orig, repl in replacements.items():
        name = name.replace(orig, repl).replace(orig.upper(), repl.capitalize())
    name = name.lower()
    name = name.replace(" ", "_")
    name = re.sub(r"[^a-z0-9_]", "", name)  # Keep only alphanum + underscore
    return name

def extract_colors_from_soup(soup):
    color_data = []
    for span in soup.find_all("span", style=True):
        style = span.get("style", "")
        if "color" in style:
            match = re.search(r"color:\s*([^;]+)", style)
            if match:
                color = match.group(1).strip().lower()
                text = span.get_text(strip=True)
                if color not in {"black", "rgb(0, 0, 0)", "#000", "#000000"}:
                    color_data.append({
                        "text": text,
                        "color": color
                    })
    return color_data
