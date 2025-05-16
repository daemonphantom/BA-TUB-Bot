import os, json, re, time, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .utils.utils import slugify, get_logger
from .crawler_quiz_questions import parse_question_blocks
from .crawler_quiz_results import _can_show_review, _extract_attempt_and_cmid, _finish_attempt, _parse_review_blocks

logger   = get_logger(__name__)
BASE_URL = "https://isis.tu-berlin.de"

def list_quizzes(driver, course_id):
    index_url = f"{BASE_URL}/mod/quiz/index.php?id={course_id}"
    driver.get(index_url)
    try:
        WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.generaltable"))
        )
    except Exception:
        logger.warning("⚠️  Keine Quiz-Tabelle gefunden.")
        return []
    soup  = BeautifulSoup(driver.page_source, "html.parser")
    table = soup.find("table", class_="generaltable")
    if not table:
        return []
    quizzes = []
    for row in table.select("tbody tr"):
        try:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue  # Überspringe unvollständige oder dekorative Zeilen

            link  = cells[1].find("a")
            title = link.text.strip()
            url   = urljoin(index_url, link["href"])
            q_id  = parse_qs(urlparse(url).query).get("id", [""])[0]
            quizzes.append({"title": title, "url": url, "id": q_id})
        except Exception as e:
            logger.warning(f"⚠️  Zeile übersprungen: {e}")
    return quizzes

def parse_view_meta(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    desc_div = soup.select_one("div.activity-description #intro, div.activity-description")
    description = desc_div.get_text(" ", strip=True) if desc_div else ""
    time_limit, grading, passing = "", "", ""
    for p in soup.select("div.quizinfo p"):
        txt = p.get_text(" ", strip=True)
        if txt.startswith("Zeitbegrenzung"):
            time_limit = txt.split(":", 1)[1].strip()
        elif txt.startswith("Bewertungsmethode"):
            grading = txt.split(":", 1)[1].strip()
        elif txt.startswith("Bestehensgrenze"):
            passing = txt.split(":", 1)[1].strip()
    return description, time_limit, grading, passing

def is_last_page(soup):
    next_btn = soup.select_one("input[name='next']")
    if not next_btn:
        return True
    hidden = soup.select_one("input[name='nextpage']")
    return hidden and hidden.get("value") == "-1"

def crawl_quiz(driver, quiz, save_dir, course_id, idx):
    logger.info(f"🎯 Quiz: {quiz['title']}")
    driver.get(quiz["url"])
    desc, time_limit, grading, passing = parse_view_meta(driver)

    # Versuche, cmid & sesskey aus dem Form zu extrahieren und direkte Start-URL zu bauen
    try:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        form = soup.find("form", action=re.compile(r"startattempt\.php"))
        cmid = form.find("input", {"name": "cmid"}).get("value")
        sesskey = form.find("input", {"name": "sesskey"}).get("value")
        attempt_url = f"{BASE_URL}/mod/quiz/startattempt.php?cmid={cmid}&sesskey={sesskey}&page=0"
        logger.info(f"🔗 Umgehen Popup — öffne direkt: {attempt_url}")
        driver.get(attempt_url)

        # Jetzt nochmal "Versuch beginnen" im neuen Kontext klicken
        submit_btns = driver.find_elements(By.ID, "id_submitbutton")
        if submit_btns:
            try:
                WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.ID, "id_submitbutton"))
                ).click()
            except Exception as e:
                logger.warning(f"⚠️  Submit-Button konnte nicht geklickt werden: {e}")
        else:
            logger.info("✅ Kein zusätzlicher Submit-Button nötig - Quiz beginnt sofort.")

    except Exception as e:
        logger.warning(f"⚠️  Konnte Start-Attempt-URL nicht öffnen: {e}")

    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "responseform"))
        )
    except Exception:
        logger.error("❌ Attempt-Seite lädt nicht.")
        return None, 0

    # Seiten durchgehen
    all_questions = []
    pagecounter = 0
    while True:
        html = driver.page_source
        all_questions.extend(parse_question_blocks(html, driver=driver, base_url=BASE_URL, data_dir="b_data", course_id=course_id))
        soup = BeautifulSoup(html, "html.parser")
        if is_last_page(soup):
            break
        try:
            next_btn = driver.find_element(By.CSS_SELECTOR, "input[name='next']")
            driver.execute_script("arguments[0].click();", next_btn)
            pagecounter += 1
            WebDriverWait(driver, 4).until(
                EC.text_to_be_present_in_element_value(
                    (By.CSS_SELECTOR, "input[name='thispage']"), str(pagecounter))
            )
        except Exception:
            logger.warning("⚠️  Konnte nicht zur nächsten Seite navigieren.")
            break

    review_blocks = []
    if _can_show_review(grading):
        # retrieve attempt & cmid from the last page we just parsed
        attempt_id, cmid_val = _extract_attempt_and_cmid(soup, cmid)
        if attempt_id:
            try:
                _finish_attempt(driver, attempt_id, cmid_val)
                review_blocks = _parse_review_blocks(driver.page_source, data_dir=save_dir, course_id=course_id, cmid=cmid_val, driver=driver)
                logger.info(f"📋 Review-Seite geparsed - {len(review_blocks)} outcomes gefunden.")
            except Exception as e:
                logger.warning(f"⚠️  Review-Seite konnte nicht geladen werden: {e}")

    safe = slugify(quiz["title"])
    path = os.path.join(save_dir, f"{course_id}_quiz_{idx:02d}_{safe}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "title"          : quiz["title"],
            "description"    : desc,
            "time_limit"     : time_limit,
            "grading_method" : grading,
            "passing_grade"  : passing,
            "question_count" : len(all_questions),
            "questions"      : all_questions,
            "review"         : review_blocks
        }, f, ensure_ascii=False, indent=2)
    return path, len(all_questions)


def crawl(driver, quiz_folder):
    course_id = parse_qs(urlparse(driver.current_url).query).get("id", ["unknown"])[0]
    if course_id in ["unknown", "1"]:
        logger.error("⚠️  Ungültige Kurs-ID - abbrechen.")
        return []
    quizzes = list_quizzes(driver, course_id)
    summary = []
    for idx, q in enumerate(quizzes, start=1):
        res_path, q_count = crawl_quiz(driver, q, quiz_folder, course_id, idx)
        if res_path:
            summary.append({
                "title"     : q["title"],
                "questions" : q_count,
                "saved_to"  : res_path
            })
    logger.info(f"✅ {len(summary)} Quiz-Dateien in {quiz_folder} gespeichert")
    return summary

