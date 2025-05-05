"""document_crawler.py

Crawler for *single‑file* Moodle resources using the **document / text / markup**
icons:

    /f/document   → typically PDFs, DOCX, PPTX …
    /f/text       → plain‑text or SQL scripts
    /f/markup     → LaTeX, XML, Markdown, …

Behaviour is identical to `resources_crawler_improved.py` except for:

* Target icon whitelist is `ICON_SELECTORS` below.
* Files are stored beneath a **files_docs/** sub‑folder.
* If the initial `view.php` page does *not* redirect but renders an HTML page
  (e.g. "stored file – click to download"), we scrape the first hyperlink that
  points to `pluginfile.php`.
"""
from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from typing import List
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from ..utils import get_course_id_from_url, get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ICON_SELECTORS = "img[src*='/f/document'], img[src*='/f/text'], img[src*='/f/markup']"
SUBFOLDER = "files"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _safe_filename(url: str) -> str:
    """Return the filename part of *url*; default to .bin if missing."""
    name = Path(unquote(urlparse(url).path)).name
    # Common 'fake file' extensions that just point somewhere else
    if any(name.endswith(ext) for ext in [".webloc", ".url", ".desktop", ".lnk", ".link"]):
        return None
    if "." not in name:
        name += ".bin"
    return name


def _download(session: requests.Session, url: str, dst: Path) -> bool:
    """Stream *url* → *dst* using *session*."""
    try:
        resp = session.get(url, stream=True, timeout=20, allow_redirects=True)
        resp.raise_for_status()
        dst.parent.mkdir(parents=True, exist_ok=True)
        with open(dst, "wb") as fh:
            for chunk in resp.iter_content(chunk_size=32_768):
                fh.write(chunk)
        return True
    except (requests.Timeout, requests.RequestException) as exc:
        logger.warning("⚠️ Download failed for %s – %s", url, exc)
        return False


# ---------------------------------------------------------------------------
# main crawler
# ---------------------------------------------------------------------------

def crawl(driver, metadata_path: str) -> List[dict]:
    course_id = get_course_id_from_url(driver.current_url)

    # 1) detect grids with document/text/markup icons
    grids = [g for g in driver.find_elements(By.CSS_SELECTOR, ".activity-grid")
             if g.find_elements(By.CSS_SELECTOR, ICON_SELECTORS)]
    logger.info("Found %d document‑type grids", len(grids))

    # 2) build requests session from Selenium cookies
    session = requests.Session()
    for c in driver.get_cookies():
        session.cookies.set(c["name"], c["value"])
    session.headers.update({"User-Agent": driver.execute_script("return navigator.userAgent;")})

    downloads: List[dict] = []
    seen_urls = set()

    for idx, grid in enumerate(grids, 1):
        try:
            a_tag = grid.find_element(By.XPATH, ".//a[contains(@href,'/mod/resource/view.php')]")
            view_url = a_tag.get_attribute("href")
            if not view_url or view_url in seen_urls:
                continue
            seen_urls.add(view_url)

            # title cleanup (remove trailing "\nDatei")
            try:
                title_span = a_tag.find_element(By.CSS_SELECTOR, ".instancename")
                title = title_span.text.rsplit("\nDatei", 1)[0].strip()
            except Exception:
                title = a_tag.text.replace("\nDatei", "").strip()

            # ------------------------------------------------------------
            # resolve to actual file
            # ------------------------------------------------------------
            res = session.get(view_url, stream=True, timeout=20, allow_redirects=True)
            res.raise_for_status()
            download_url = res.url

            # Case A: we already got the file (redirect happened)
            content_type = res.headers.get("Content-Type", "")
            is_html = content_type.startswith("text/html")

            if is_html and "pluginfile.php" not in download_url:
                # Case B: Moodle rendered a stub page – scrape first pluginfile link
                soup = BeautifulSoup(res.text, "html.parser")
                link = soup.select_one("a[href*='pluginfile.php']")
                if not link:
                    logger.warning("⚠️ No pluginfile link found in %s", view_url)
                    continue
                download_url = link.get("href")

            if "pluginfile.php" not in download_url:
                logger.warning("⚠️ Skipping non‑pluginfile resource %s", download_url)
                continue

            # 3b. Build target filename →  {courseID}_{NNN}_document.<ext>
            orig_filename = _safe_filename(download_url)
            if orig_filename is None:
                logger.info("⏭️  Skipping link file %s", download_url)
                continue

            ext = Path(orig_filename).suffix or ".bin"
            filename = f"{course_id}_{idx:03d}_document{ext}"
            dst_dir = Path(metadata_path).with_name(SUBFOLDER)
            dst_path = dst_dir / filename


            # if we already have binary body (redirect path) and it's not HTML, use it
            ok = False
            if not is_html and "/pluginfile.php" in download_url:
                try:
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(dst_path, "wb") as fh:
                        for chunk in res.iter_content(chunk_size=32_768):
                            fh.write(chunk)
                    ok = True
                except Exception as exc:
                    logger.debug("Inline save failed: %s", exc)

            if not ok:
                ok = _download(session, download_url, dst_path)

            if ok:
                logger.info("✅ Saved %s", dst_path)
                downloads.append({
                    "title": title,
                    "moodle_url": view_url,
                    "download_url": download_url,
                    "saved_filename": dst_path.name,
                    "saved_path": str(dst_path),
                })

        except (NoSuchElementException, requests.RequestException) as exc:
            logger.warning("⚠️ Failure processing grid – %s", exc)
            continue

    # 4) write metadata
    Path(metadata_path).parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as fp:
        json.dump(downloads, fp, ensure_ascii=False, indent=2)

    return downloads
