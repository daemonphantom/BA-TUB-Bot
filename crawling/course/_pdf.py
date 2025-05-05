"""document_crawler.py  ‑ v2.4

Downloads *single‑file* Moodle resources shown with the **document / text / markup / pdf**
icons.  Handles:
  • classic *Resource* activities
  • *Folder* activities
  • *URL* activities that point to external PDFs (e.g. Git cheat‑sheet)  

Changes (2025‑05‑05 22:45)
-------------------------
* **`/f/pdf` icon added** → classic PDF grids are now picked up.
* XPath extended to include **`/mod/url/view.php`**.
* `_extract_redirect_from_html` now returns the first **.pdf** URL found in
  meta‑refresh or JS `window.location`.
* Anchor scraping looks for `.pdf` as well as `pluginfile.php` links.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from ..utils import get_course_id_from_url, get_logger

logger = get_logger(__name__)

# include PDF icon
ICON_SELECTORS = (
    "img[src*='/f/document'], img[src*='/f/text'], img[src*='/f/markup'], "
    "img[src*='/f/pdf']"
)
SUBFOLDER = "files"

# ‑‑‑ helpers ‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑

def _safe_filename(url: str) -> Optional[str]:
    name = Path(unquote(urlparse(url).path)).name
    if any(name.endswith(ext) for ext in (".webloc", ".url", ".desktop", ".lnk", ".link")):
        return None
    if "." not in name:
        name += ".bin"
    return name


def _download(session: requests.Session, url: str, dst: Path) -> bool:
    try:
        with session.get(url, stream=True, timeout=25, allow_redirects=True) as resp:
            resp.raise_for_status()
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=32_768):
                    fh.write(chunk)
        return True
    except requests.RequestException as exc:
        logger.warning("⚠️  Download failed for %s – %s", url, exc)
        return False


def _extract_redirect_from_html(html: str) -> Optional[str]:
    """Return first PDF or pluginfile URL found in meta‑refresh or JS redirects."""
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
    if meta and (content := meta.get("content")) and "url=" in content.lower():
        url_part = content.split("url=", 1)[1].strip(" '")
        if url_part.lower().endswith(".pdf") or "pluginfile.php" in url_part:
            return url_part
    m = re.search(r"window\.location(?:\.href)?\s*=\s*['\"]([^'\"]+(?:pluginfile\.php|\.pdf)[^'\"]*)", html, re.I)
    return m.group(1) if m else None


# ‑‑‑ main crawler ‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑‑

def crawl(driver, metadata_path: str) -> List[dict]:
    course_id = get_course_id_from_url(driver.current_url)

    grids = [g for g in driver.find_elements(By.CSS_SELECTOR, ".activity-grid")
             if g.find_elements(By.CSS_SELECTOR, ICON_SELECTORS)]
    logger.info("Found %d document‑type grids", len(grids))

    session = requests.Session()
    for c in driver.get_cookies():
        session.cookies.set(c["name"], c["value"])
    session.headers.update({"User-Agent": driver.execute_script("return navigator.userAgent;")})

    downloads: List[dict] = []
    seen: set[str] = set()

    for idx, grid in enumerate(grids, 1):
        try:
            try:
                a_tag = grid.find_element(
                    By.XPATH,
                    ".//a[contains(@href,'/mod/resource/view.php') or contains(@href,'/mod/folder/view.php') or contains(@href,'/mod/url/view.php')]"
                )
                view_url = a_tag.get_attribute("href")
                if not view_url or view_url in seen:
                    continue
                seen.add(view_url)

                title = (a_tag.text or "").replace("\nDatei", "").replace("\nLink/URL", "").strip()
                res = session.get(view_url, stream=True, timeout=20, allow_redirects=True)
                res.raise_for_status()
                final_url = res.url
                ctype = res.headers.get("Content-Type", "").lower()

                # direct binary (PDF/DOCX) served by view.php or by 302 redirect
                if not ctype.startswith("text/html") and ("application/" in ctype or final_url.lower().endswith(".pdf")):
                    orig = _safe_filename(final_url)
                    if orig:
                        dst = Path(metadata_path).with_name(SUBFOLDER) / f"{course_id}_{idx:03d}_document{Path(orig).suffix or '.bin'}"
                        if _download(session, final_url, dst):
                            logger.info("✅ Saved %s", dst)
                            downloads.append({
                                "title": title,
                                "moodle_url": view_url,
                                "download_url": final_url,
                                "saved_filename": dst.name,
                                "saved_path": str(dst),
                            })
                    continue

                html = res.text  # stub page
            except NoSuchElementException:
                view_url = driver.current_url
                title = f"{course_id}_{idx:03d}"
                html = grid.get_attribute("innerHTML")

            soup = BeautifulSoup(html, "html.parser")
            links = soup.select("a[href*='pluginfile.php'], a[href$='.pdf']")

            if not links:
                redirect_url = _extract_redirect_from_html(html)
                if redirect_url:
                    links = [BeautifulSoup(f'<a href="{redirect_url}"></a>', "html.parser").a]

            if not links:
                logger.warning("⚠️  No PDF/pluginfile links found in %s", view_url)
                continue

            for subidx, link in enumerate(links, 1):
                dl_url = link["href"]
                orig = _safe_filename(dl_url)
                if orig is None:
                    logger.info("⏭️  Skipping pseudo link %s", dl_url)
                    continue

                dst = Path(metadata_path).with_name(SUBFOLDER) / f"{course_id}_{idx:03d}_{subidx:02d}_document{Path(orig).suffix or '.bin'}"
                if _download(session, dl_url, dst):
                    logger.info("✅ Saved %s", dst)
                    downloads.append({
                        "title": f"{title} (file {subidx})",
                        "moodle_url": view_url,
                        "download_url": dl_url,
                        "saved_filename": dst.name,
                        "saved_path": str(dst),
                    })

        except requests.RequestException as exc:
            logger.warning("⚠️  HTTP error – %s", exc)
            continue

    Path(metadata_path).parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as fp:
        json.dump(downloads, fp, ensure_ascii=False, indent=2)

    return downloads
