import os
import requests
import re
import json
import html
from urllib.parse import urljoin, unquote, urlparse
from bs4 import BeautifulSoup
from PIL import Image  # type: ignore
from .utils.utils import download_image, get_logger
from xml.etree import ElementTree as ET


logger = get_logger(__name__)

USER_AGENT_HEADER = {
    "User-Agent": "Mozilla/5.0 (compatible; moodle-crawler)"
}

def download_image_moodle(url: str, data_dir: str, course_id: str, identifier: str, driver=None):
    #logger.info(f"📥 Versuche Bild herunterzuladen: {url}")

    parsed = urlparse(url)
    ext = os.path.splitext(unquote(parsed.path))[1].lower()
    ext = ext if ext in [".png", ".jpg", ".jpeg", ".gif", ".svg"] else ".bin"
    subpath = unquote(parsed.path.split("pluginfile.php")[-1].lstrip("/"))
    save_dir = os.path.join(data_dir, f"course_{course_id}", "quizzes", "ddimg")
    path = os.path.join(save_dir, subpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path):
        logger.info(f"✅ Bild bereits vorhanden: {path}")
        return path

    try:
        if driver and hasattr(driver, "requests"):
            matching_requests = [r for r in driver.requests if url in r.url and r.response]
            if matching_requests:
                response = max(matching_requests, key=lambda r: len(r.response.body))
                with open(path, "wb") as f:
                    f.write(response.response.body)
                logger.info(f"✅ Erfolgreich gespeichert: {path}")
                return path
            else:
                logger.warning("⚠️ Kein passender Request im Netzwerk-Log gefunden")
        else:
            logger.warning("⛔ Driver hat kein 'requests' Attribut oder ist nicht vorhanden — breche Download ab")
    except Exception as e:
        logger.warning(f"⚠️ Image download failed: {e}")
    return None

def parse_ddimageortext(qdiv, base_url, data_dir, course_id, driver=None):
    try:
        ddinfo = {}

        bg = qdiv.select_one("div.ddarea img.dropbackground")
        if bg:
            bg_url = urljoin(base_url, bg["src"])
            logger.info(f"🎯 Hintergrundbild erkannt: {bg_url}")
            bg_path = download_image_moodle(bg_url, data_dir, course_id, "background", driver)
            ddinfo["background"] = bg_path or bg_url

            try:
                if bg_path and os.path.exists(bg_path) and bg_path.lower().endswith((".png", ".jpg", ".jpeg")):
                    with Image.open(bg_path) as img:
                        ddinfo["bg_size"] = img.size
                        #logger.info(f"📐 Bildgröße: {img.size}")
                elif bg_path and os.path.exists(bg_path) and bg_path.lower().endswith(".svg"):
                    ddinfo["bg_size"] = get_svg_size(bg_path)
                elif not bg_path:
                    logger.warning(f"⚠️ Hintergrundbild konnte nicht gespeichert werden: {bg_url}")
                else:
                    logger.info(f"ℹ️  Bildgröße wird für SVG oder nicht unterstütztes Format übersprungen: {bg_path}")
            except Exception as e:
                logger.warning(f"⚠️  konnte Bildgröße nicht bestimmen: {e}")

        zones = []
        dz_container = qdiv.select_one("div.dropzones")
        if dz_container and dz_container.has_attr("data-place-info"):
            try:
                #logger.info("📌 Dropzone-Informationen extrahieren")
                place_info = json.loads(html.unescape(dz_container["data-place-info"]))
                for no, meta in place_info.items():
                    zones.append({
                        "place": int(no),
                        "group": f"group{meta['group']}",
                        "xy": [int(meta["xy"][0]), int(meta["xy"][1])]
                    })
            except Exception as e:
                logger.warning(f"⚠️  Dropzones konnten nicht geparst werden: {e}")
        ddinfo["dropzones"] = zones

        choices = []
        seen = set()
        for item in qdiv.select("div.draghomes .draghome"):
            group = next((c for c in item.get("class", []) if c.startswith("group")), "")
            choice = next((c for c in item.get("class", []) if c.startswith("choice")), "")

            content = ""
            loc = None
            if item.name == "img":
                src = urljoin(base_url, item["src"])
                key = (group, choice, src)
                if key in seen:
                    continue
                seen.add(key)
                #logger.info(f"🔹 Finde Draggable-Bild: {src}")
                loc = download_image_moodle(src, data_dir, course_id, f"{group}_{choice}", driver=driver) or src
            else:
                content = item.get_text(" ", strip=True)
                key = (group, choice, content)
                if key in seen:
                    continue
                seen.add(key)
                #logger.info(f"🔸 Finde Draggable-Text: {content}")

            choices.append({
                "group": group,
                "choice": int(choice.replace("choice", "")) if choice else None,
                "file": loc,
                "text": content,
                "alt": item.get("alt", "")
            })

        ddinfo["choices"] = choices
        return ddinfo

    except Exception as e:
        logger.warning(f"⚠️  ddimageortext konnte nicht verarbeitet werden: {e}")
        return {}


def get_svg_size(svg_path):
    try:
        with open(svg_path, "r", encoding="utf-8") as f:
            tree = ET.parse(f)
            root = tree.getroot()
            width = root.attrib.get("width")
            height = root.attrib.get("height")
            viewbox = root.attrib.get("viewBox")

            def _strip(val):
                return float(re.sub(r"[a-zA-Z%]+$", "", val)) if val else None

            if width and height:
                return int(_strip(width)), int(_strip(height))
            elif viewbox:
                parts = viewbox.split()
                if len(parts) == 4:
                    return int(float(parts[2])), int(float(parts[3]))
    except Exception as e:
        logger.warning(f"⚠️ SVG size konnte nicht bestimmt werden: {e}")
    return None