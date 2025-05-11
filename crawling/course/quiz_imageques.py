import os
import re
import html
from urllib.parse import urljoin, unquote, urlparse
from bs4 import BeautifulSoup, NavigableString, Tag
from ..utils import get_logger
from .quiz_ddimageortext import download_image_moodle
import base64

logger = get_logger(__name__)


def parse_checkbox_multichoice(qdiv, base_url, data_dir, course_id, driver=None):
    try:
        qtext_el = qdiv.select_one("div.qtext")
        qtext = qtext_el.get_text(" ", strip=True) if qtext_el else ""

        # Fragebild (falls vorhanden)
        image = None
        img_tag = qtext_el.select_one("img") if qtext_el else None
        if img_tag:
            img_url = urljoin(base_url, img_tag.get("src"))
            image = download_image_moodle(img_url, data_dir, course_id,
                                          "checkbox_multichoice", driver=driver) or img_url

        options = []
        for idx, row in enumerate(qdiv.select("div.answer > div")):
            label_container = row.select_one("div[data-region='answer-label']")
            if not label_container:
                continue

            img = label_container.select_one("img")
            if img:  # Bild‑Option -------------------------------------------------
                src = img.get("src")
                if src.startswith("data:image"):
                    loc = save_base64_image(src, data_dir, course_id,
                                            f"checkbox_option_{idx}")
                    options.append(loc or src)
                else:
                    full = urljoin(base_url, src)
                    loc = download_image_moodle(full, data_dir, course_id,
                                                f"checkbox_option_{idx}", driver=driver)
                    options.append(loc or full)
            else:     # Text‑Option (mit evtl. <u>) ------------------------------
                plain, under = extract_text_and_underlined(label_container)
                opt = {"text": plain}
                if under:
                    opt["underlined"] = under
                options.append(opt)
        return {
            "text": qtext,
            "image": image,
            "type": "image_multichoice" if image or any(
                isinstance(o, str) and o.lower().endswith((".png", ".jpg", ".jpeg", ".svg"))
                for o in options) else "checkbox_multichoice",
            "options": options
        }

    except Exception as e:
        logger.warning(f"⚠️ checkbox_multichoice konnte nicht verarbeitet werden: {e}")
        return {"text": "", "image": None, "type": "unknown", "options": []}



def parse_radiobutton_multichoice(qdiv, base_url, data_dir, course_id, driver=None):
    try:
        qtext_el = qdiv.select_one("div.qtext")
        qtext = qtext_el.get_text(" ", strip=True) if qtext_el else ""

        image = None
        img_tag = qtext_el.select_one("img") if qtext_el else None
        if img_tag:
            img_url = urljoin(base_url, img_tag.get("src"))
            image = download_image_moodle(img_url, data_dir, course_id,
                                          "radiobutton_multichoice", driver=driver) or img_url

        options = []
        for idx, row in enumerate(qdiv.select("div.answer > div")):
            label_container = row.select_one("div[data-region='answer-label']")
            if not label_container:
                continue

            img = label_container.select_one("img")
            if img:
                src = img.get("src")
                if src.startswith("data:image"):
                    loc = save_base64_image(src, data_dir, course_id,
                                            f"radio_option_{idx}")
                    options.append(loc or src)
                else:
                    full = urljoin(base_url, src)
                    loc = download_image_moodle(full, data_dir, course_id,
                                                f"radio_option_{idx}", driver=driver)
                    options.append(loc or full)
            else:
                plain, under = extract_text_and_underlined(label_container)
                opt = {"text": plain}
                if under:
                    opt["underlined"] = under
                options.append(opt)

        return {
            "text": qtext,
            "image": image,
            "type": "image_singlechoice" if image or any(
                isinstance(o, str) and o.lower().endswith((".png", ".jpg", ".jpeg", ".svg"))
                for o in options) else "singlechoice",
            "options": options
        }

    except Exception as e:
        logger.warning(f"⚠️ radiobutton_multichoice konnte nicht verarbeitet werden: {e}")
        return {"text": "", "image": None, "type": "unknown", "options": []}




def parse_truefalse_question(qdiv, base_url, data_dir, course_id, driver=None):
    try:
        qtext_el = qdiv.select_one("div.qtext")
        qtext = qtext_el.get_text(" ", strip=True) if qtext_el else ""

        image = extract_question_image(qdiv, base_url, data_dir, course_id, driver)

        options = []
        for label in qdiv.select("fieldset label"):
            label_text = label.get_text(" ", strip=True)
            if label_text:
                options.append(label_text)

        return {
            "text": qtext,
            "image": image,
            "type": "truefalse",
            "options": options
        }

    except Exception as e:
        logger.warning(f"⚠️ truefalse konnte nicht verarbeitet werden: {e}")
        return {
            "text": "",
            "image": None,
            "type": "unknown",
            "options": []
        }

def parse_truefalse_multi(qdiv):
    try:
        statements = []
        for row in qdiv.select("table.generaltable tr.qtype_mtf_row"):
            statement_el = row.select_one("td.optiontext")
            if statement_el:
                statement = statement_el.get_text(" ", strip=True)
                statements.append({"statement": statement, "options": ["Wahr", "Falsch"]})

        return {
            "text": "Geben Sie an, ob die folgenden Aussagen Wahr oder Falsch sind.",
            "image": None,
            "type": "truefalse_multi",
            "options": statements
        }
    except Exception as e:
        logger.warning(f"⚠️ truefalse_multi konnte nicht verarbeitet werden: {e}")
        return {
            "text": "",
            "image": None,
            "type": "unknown",
            "options": []
        }


def extract_question_image(qdiv, base_url, data_dir, course_id, driver=None):
    qtext_el = qdiv.select_one("div.qtext")
    img_tag = qtext_el.select_one("img") if qtext_el else None
    if img_tag:
        img_url = urljoin(base_url, img_tag.get("src"))
        logger.info(f"🖼️ Frage enthält Bild: {img_url}")
        return download_image_moodle(img_url, data_dir, course_id, "questionimage", driver=driver) or img_url
    return None




def save_base64_image(data_uri, data_dir, course_id, filename):
    try:
        header, encoded = data_uri.split(",", 1)
        file_ext = header.split(";")[0].split("/")[1]  # e.g., "image/png"

        subfolder = os.path.join("quizzes", "ddimg", "base64")
        path = os.path.join(data_dir, f"course_{course_id}", subfolder, f"{filename}.{file_ext}")
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "wb") as f:
            f.write(base64.b64decode(encoded))

        return path
    except Exception as e:
        logger.warning(f"⚠️ Base64-Bild konnte nicht gespeichert werden: {e}")
        return None


def extract_text_and_underlined(tag):
    text_parts   = []
    underlined   = []
    offset       = 0

    def walk(node, inside_u=False):
        nonlocal offset
        if isinstance(node, NavigableString):
            content = str(node)
            if inside_u and content.strip():
                underlined.append({
                    "text":  content,
                    "start": offset,
                    "end":   offset + len(content)
                })
            text_parts.append(content)
            offset += len(content)
        elif isinstance(node, Tag):
            if node.name == "u":
                for child in node.children:
                    walk(child, inside_u=True)
            else:
                for child in node.children:
                    walk(child, inside_u=inside_u)

    walk(tag)
    return "".join(text_parts), underlined 