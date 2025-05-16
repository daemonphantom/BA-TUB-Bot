from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
import os, re, html
from .misc import get_logger
from .quiz_ddimageortext import download_image_moodle
from .utils.utils import download_image 
from .quiz_questions import extract_text_and_underlined, save_base64_image

logger = get_logger(__name__)

# ── NEW HELPERS ────────────────────────────────────────────────────────────────
def _can_show_review(grading_method: str) -> bool:
    """Returns True if Moodle will show a review page after submitting."""
    return "Bester Versuch" in grading_method  # feel free to widen the check


def _extract_attempt_and_cmid(soup: BeautifulSoup, fallback_cmid: str) -> tuple[str, str]:
    """Pull attempt-id and cmid from the last page of the quiz."""
    attempt = soup.select_one("input[name='attempt']")
    cmid    = soup.select_one("input[name='cmid']")
    return (attempt["value"] if attempt else ""), (cmid["value"] if cmid else fallback_cmid)


def _finish_attempt(driver, attempt_id: str, cmid: str) -> None:
    """Navigiert zur summary.php, klickt auf 'Abgeben' und bestätigt (Modal).
    Fallback: Erkennt auch automatische Weiterleitung zur review.php.
    """
    BASE_URL = "https://isis.tu-berlin.de"
    summary_url = f"{BASE_URL}/mod/quiz/summary.php?attempt={attempt_id}&cmid={cmid}"
    driver.get(summary_url)
    logger.info(f"📄 Summary geöffnet: {summary_url}")

    # 1. Klick auf „Abgeben“-Button auf der Summary-Seite
    try:
        abgeben_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "form#frm-finishattempt button[type='submit']"))
        )
        abgeben_button.click()
        logger.info("✅ Abgeben geklickt")
    except Exception as e:
        logger.warning(f"❌ Konnte nicht auf 'Abgeben' klicken: {e}")
        raise e

        
    # 2. Versuch Modal zu bestätigen (wenn es erscheint)
    try:
        confirm_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "div.modal-footer [data-action='save']"))
        )
        confirm_button.click()
        logger.info("✅ Modal bestätigt")
    except Exception as e:
        logger.info(f"ℹ️ Konnte nicht bestätigen - evtl. automatische Weiterleitung")
    
    # 3. Egal ob Modal oder nicht: Warte auf Weiterleitung zu review.php
    try:
        WebDriverWait(driver, 6).until(EC.url_contains("review.php"))
        logger.info("🔁 Weiterleitung zur Review-Seite erkannt")
    except Exception as e:
        current_url = driver.current_url
        if "review.php" in current_url:
            logger.info("🔁 Bereits auf der Review-Seite - Modal wurde evtl. automatisch übersprungen")
        else:
            logger.error(f"❌ Keine Weiterleitung zur Review-Seite: {e}")
            raise e


def _parse_review_blocks(html: str, data_dir: str, course_id: str, cmid: str, driver=None) -> list[dict]:
    WebDriverWait(driver, 20).until(
        lambda d: all(img.get_attribute("src") for img in d.find_elements(By.CSS_SELECTOR, "div.outcome img"))
    )

    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    blocks = []
    questions = soup.select("div.que")
    logger.info(f"📦 Anzahl gefundener Fragenblöcke: {len(questions)}")

    for idx, q in enumerate(questions):
        logger.info(f"\n--- 🎯 Frageblock {idx + 1} ---")

        qnum_tag = q.select_one("h3.no .qno")
        if not qnum_tag:
            logger.info("⚠️ Keine Frage-Nummer gefunden – übersprungen")
            continue
        try:
            number = int(qnum_tag.text.strip())
            logger.info(f"🆔 Frage Nummer: {number}")
        except ValueError:
            logger.warning("❌ Fehler beim Parsen der Nummer")
            continue

        outcome = q.select_one("div.outcome")
        if not outcome:
            # Sonderfall: Multianswer-Fragen ohne 'outcome', aber mit eingebettetem Feedback in subquestions
            if q.get("class") and "multianswer" in q["class"]:
                logger.info(f"ℹ️ Multianswer-Frage erkannt (kein outcome, aber subquestions vorhanden)")
                multianswer_feedbacks = _extract_multianswer_feedback(q)
                question_text_tag = q.select_one("div.formulation")
                if question_text_tag:
                    question_text = question_text_tag.get_text(" ", strip=True)
                else:
                    question_text = ""

                blocks.append({
                    "number": number,
                    "multianswers": multianswer_feedbacks
                })
                continue
            else:
                logger.warning(f"⚠️ Kein 'outcome' für Frage {number} gefunden – übersprungen")
                continue

        right = outcome.select_one(".rightanswer")
        if right:
            logger.info(f"✅ Rightanswer gefunden für Frage {number}")
        else:
            logger.info(f"ℹ️ Keine rightanswer für Frage {number}")

        structured = _extract_structured_answers(right) if right else []

        feedback_div = outcome.select_one(".generalfeedback")
        if feedback_div:
            logger.info(f"💬 Generalfeedback vorhanden für Frage {number}")
        general_feedback = _extract_general_feedback(feedback_div) if feedback_div else []

        img_tags = outcome.select("img")
        logger.info(f"🖼️ {len(img_tags)} Bild(er) gefunden in Frage {number}")
        images = []

        for i, img in enumerate(img_tags):
            src = img.get("src", "")
            logger.info(f"🔗 Bildquelle {i+1}: {src[:80]}...")
            if not src:
                logger.warning(f"⚠️ Kein src für Bild {i+1} in Frage {number}")
                continue
            try:
                identifier = f"{cmid}_{number}_img{i+1}"
                if src.startswith("data:image"):
                    local_path = save_base64_image(src, data_dir, course_id, identifier)
                    logger.info(f"💾 Base64 gespeichert: {local_path}")
                else:
                    local_path = download_image(src, os.path.join(data_dir, f"course_{course_id}", "quizzes/ddimg"), identifier, driver=driver)
                    logger.info(f"💾 Extern gespeichert: {local_path}")
                if local_path:
                    rel_path = os.path.relpath(local_path, os.path.join(data_dir, f"course_{course_id}", "quizzes"))
                    images.append(rel_path)
                else:
                    logger.warning(f"❌ Bild konnte NICHT gespeichert werden: {src}")
            except Exception as e:
                logger.warning(f"❌ Fehler beim Speichern von Bild {i+1}: {e}")

        blocks.append({
            "number": number,
            **({"general_feedback": general_feedback} if general_feedback else {}),
            "right_answer": structured,
            **({"images": images} if images else {})
        })

        logger.info(f"✅ Block {number} abgeschlossen mit {len(images)} Bild(er)")

    logger.info(f"\n🎉 Parsing abgeschlossen – {len(blocks)} Blöcke extrahiert")
    return blocks


def _extract_structured_answers(right_div: BeautifulSoup) -> list[dict]:
    """Parst <div class='rightanswer'> in strukturierte, LLM-freundliche Antwortobjekte inkl. Unterstreichung."""
    result = []

    # Case 1: LI-Items mit Wahr/Falsch
    for li in right_div.select("li"):
        p = li.get_text(" ", strip=True)
        correctness = None
        if ": Falsch" in p:
            p = p.replace(": Falsch", "").strip()
            correctness = False
        elif ": Wahr" in p:
            p = p.replace(": Wahr", "").strip()
            correctness = True

        text, underlined = extract_text_and_underlined(li)
        result.append({
            "text": text.strip(),
            "correct": correctness,
            **({"underlined": underlined} if underlined else {})
        })

    # Case 2: Nur <p>-Tags → ER-Notation o.ä.
    if not result and right_div.select("p"):
        for p_tag in right_div.select("p"):
            text, underlined = extract_text_and_underlined(p_tag)
            if text.strip():
                result.append({
                    "text": text.strip(),
                    **({"underlined": underlined} if underlined else {})
                })

    # Case 3: Fließtext fallback
    if not result:
        text, underlined = extract_text_and_underlined(right_div)
        result.append({
            "text": text.strip(),
            **({"underlined": underlined} if underlined else {})
        })

    return result

def _extract_general_feedback(feedback_div: BeautifulSoup) -> list[dict]:
    """Parst <div class='generalfeedback'> in strukturierte text + underlined Blöcke."""
    result = []
    if not feedback_div:
        return result

    # 1. Listenitems (<li>)
    for li in feedback_div.select("li"):
        text, underlined = extract_text_and_underlined(li)
        if text.strip():
            result.append({
                "text": text.strip(), 
                **({"underlined": underlined} if underlined else {})
    })

    # 2. Paragraphs (<p>) wenn keine <li>
    if not result:
        for p in feedback_div.select("p"):
            text, underlined = extract_text_and_underlined(p)
            if text.strip():
                result.append({
                    "text": text.strip(), 
                    **({"underlined": underlined} if underlined else {})
    })

    # 3. Fallback auf Gesamtdom (selten)
    if not result:
        text, underlined = extract_text_and_underlined(feedback_div)
        if text.strip():
            result.append({
                "text": text.strip(), 
                **({"underlined": underlined} if underlined else {})
    })

    return result

def _extract_multianswer_feedback(question_div: BeautifulSoup) -> list[dict]:
    """
    Extrahiert strukturierte Feedbackdaten aus Cloze/Multianswer-Fragen, 
    speziell aus HTML eingebetteten JS-Attributen (Popover-Feedback).
    """
    feedbacks = []
    for idx, span in enumerate(question_div.select("span.subquestion"), start=1):
        label = span.select_one("label")
        select = span.select_one("select")
        a_tag = span.select_one("a.feedbacktrigger")

        correct_answer = None
        feedback_html = a_tag.get("data-content", "") if a_tag else ""

        if "Die richtige Antwort ist:" in feedback_html:
            match = re.search(r"Die richtige Antwort ist: (.*?)<", feedback_html)
            if match:
                correct_answer = html.unescape(match.group(1)).strip()

        feedbacks.append({
            "blank": idx,
            **({"correct_answer": correct_answer} if correct_answer else {}),
        })
    return feedbacks