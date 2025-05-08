import os, json, re, time, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from ..utils import get_logger
from .utils.utils import slugify

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

# helper -------------------------------------------------------------
def _dl(url:str, folder:str):
    """Download `url` into `folder` (created if needed) and return local path."""
    os.makedirs(folder, exist_ok=True)
    fname = re.sub(r"[^\w\-\.]+", "_", url.split("/")[-1])
    loc   = os.path.join(folder, fname)
    if not os.path.exists(loc):
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            with open(loc, "wb") as f:
                f.write(r.content)
        except Exception as e:
            logger.warning(f"⚠️  konnte Bild nicht laden {url}: {e}")
            return url   # fallback: keep remote url
    return loc
# -------------------------------------------------------------------

def parse_question_blocks(html, base_url=BASE_URL, img_dir="ddimg"):
    soup = BeautifulSoup(html, "html.parser")
    questions = []

    for qdiv in soup.select("div.que"):
        try:
            number = int(qdiv.select_one("h3 span.qno").text.strip())
            # Standardmäßiger Fragetext
            qtext_el = qdiv.select_one("div.qtext")
            qtext = qtext_el.get_text(" ", strip=True) if qtext_el else ""

            # Punkte extrahieren
            points = ""
            grade = qdiv.select_one("div.grade")
            if grade and "Erreichbare Punkte" in grade.text:
                points = grade.text.split(":", 1)[1].strip()
            elif "Nicht bewertet" in grade.text:
                points = "0"
            # ------------------------------------------------------------------
            # NEW  ➜  Drag & Drop on image or text  (ddimageortext)
            # ------------------------------------------------------------------
            if "ddimageortext" in qdiv.get("class", []):
                qtype = "ddimageortext"
                ddinfo = {}

                # background
                bg = qdiv.select_one("div.ddarea img.dropbackground")
                if bg:
                    bg_url  = urljoin(base_url, bg["src"])
                    bg_path = _dl(bg_url, img_dir)
                    ddinfo["background"] = bg_path

                # drop zones (coords & group id)
                zones = []
                for dz in qdiv.select("div.dropzone"):
                    zones.append({
                        "group" : dz["class"][1],                 # e.g. group1
                        "place" : dz["class"][2],                 # e.g. place3
                        "style" : dz.get("style","")              # contains xy + size
                    })
                ddinfo["dropzones"] = zones

                # draggable choices grouped by groupX
                choices = []
                for drag in qdiv.select("div.draghomes img.group1, \
                                          div.draghomes img.group2, \
                                          div.draghomes img.group3, \
                                          div.draghomes img.group4"):
                    drag_url  = urljoin(base_url, drag["src"])
                    drag_path = _dl(drag_url, img_dir)
                    choices.append({
                        "group" : next(c for c in drag["class"] if c.startswith("group")),
                        "choice": next(c for c in drag["class"] if c.startswith("choice")),
                        "file"  : drag_path,
                        "alt"   : drag.get("alt","")
                    })
                ddinfo["choices"] = choices

                questions.append({
                    "number": number,
                    "text"  : qtext,
                    "type"  : qtype,
                    "points": points,
                    "dd"    : ddinfo
                })
                continue


            # MATCH‑Typ (Zuordnungsfragen)
            if qdiv.select("table.answer select"):
                qtype = "match"
                options = []
                for row in qdiv.select("table.answer tr"):
                    statement_el = row.select_one("td.text")
                    select_el = row.select_one("select")
                    if not statement_el or not select_el:
                        continue
                    statement = statement_el.get_text(" ", strip=True)
                    choices = [
                        o.get_text(" ", strip=True)
                        for o in select_el.find_all("option") if o.get("value") != "0"
                    ]
                    options.append({"statement": statement, "choices": choices})

            # TRUE/FALSE MULTI (Matrix)
            elif qdiv.select("table.generaltable input[type='radio']"):
                qtype = "truefalse_multi"
                options = [
                    row.select_one("td.optiontext").get_text(" ", strip=True)
                    for row in qdiv.select("table.generaltable tr.qtype_mtf_row")
                    if row.select_one("td.optiontext")
                ]

            # CLOZE / MULTIANSWER
            elif qdiv.has_attr("class") and "multianswer" in qdiv["class"]:
                qtype = "multianswer"
                form_div = qdiv.select_one("div.formulation")
                options = []

                if form_div:
                    for h in form_div.select("h4.accesshide"):
                        h.decompose()
                    for btn in form_div.select("button.submit"):
                        btn.decompose()

                    tmp = BeautifulSoup(str(form_div), "html.parser")
                    for i, sub in enumerate(tmp.select("span.subquestion"), start=1):
                        sub.replace_with(f"[[{i}]]")
                    qtext = tmp.get_text(" ", strip=True)

                    for i, select in enumerate(qdiv.select("select"), start=1):
                        choice_texts = [
                            o.get_text(" ", strip=True)
                            for o in select.find_all("option") if o.get_text(strip=True)
                        ]
                        options.append({
                            "blank": i,
                            "choices": choice_texts
                        })

            # MULTICHOICE (Einfachauswahl)
            elif qdiv.select("div.answer input[type='radio']"):
                qtype = "multichoice"
                options = [
                    div.select_one("div.flex-fill").get_text(" ", strip=True)
                    for div in qdiv.select("div.answer > div")
                    if div.select_one("div.flex-fill")
                ]

            # SHORTANSWER
            elif qdiv.select("input[type='text']"):
                qtype = "shortanswer"
                options = []

            # Default fallback
            else:
                qtype = "unknown"
                options = []

            questions.append({
                "number": number,
                "text":   qtext,
                "type":   qtype,
                "points": points,
                "options": options
            })

        except Exception as e:
            logger.warning(f"⚠️  Frage {qdiv.get('id', '?')} konnte nicht gelesen werden: {e}")

    return questions




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

    # Merke aktuelles Fenster
    main_window = driver.current_window_handle

    try:
        start_btn = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".quizstartbuttondiv button, .singlebutton.quizstartbuttondiv button"))
        )
        start_btn.click()
    except Exception:
        logger.warning("⚠️  Kein Start-Button für dieses Quiz.")
        return None, 0

    # ❗ Versuche, cmid & sesskey aus dem Form zu extrahieren und direkte Start-URL zu bauen
    try:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        form = soup.find("form", action=re.compile(r"startattempt\.php"))
        cmid = form.find("input", {"name": "cmid"}).get("value")
        sesskey = form.find("input", {"name": "sesskey"}).get("value")
        attempt_url = f"{BASE_URL}/mod/quiz/startattempt.php?cmid={cmid}&sesskey={sesskey}"
        logger.info(f"🔗 Umgehen Popup — öffne direkt: {attempt_url}")
        driver.get(attempt_url)

        # Jetzt nochmal "Versuch beginnen" im neuen Kontext klicken
        WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.ID, "id_submitbutton"))
        ).click()
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
        all_questions.extend(parse_question_blocks(html))
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
            "questions"      : all_questions
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
        res_path, q_cnt = crawl_quiz(driver, q, quiz_folder, course_id, idx)
        if res_path:
            summary.append({
                "title"     : q["title"],
                "questions" : q_cnt,
                "saved_to"  : res_path
            })
    logger.info(f"✅ {len(summary)} Quiz-Dateien in {quiz_folder} gespeichert")
    return summary
