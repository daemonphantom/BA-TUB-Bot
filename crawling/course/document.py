"""document_crawler.py – v2.6

Downloads *single-file* Moodle resources displayed with **document / text / markup / pdf / url** icons.
Handles:
  • Resource, Folder, and URL activities (internal and external)  
  • Direct 302 redirects to PDFs  
  • view.php pages that require `?redirect=1`  
  • HTML stubs / folder tables with multiple links  
  • Meta‑refresh or JS window.location redirects
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

# Icons we care about
ICON_SELECTORS = (
    "img[src*='/f/document'], img[src*='/f/text'], img[src*='/f/markup'], "
    "img[src*='/f/pdf']"
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _safe_filename(url: str) -> Optional[str]:
    name = Path(unquote(urlparse(url).path)).name
    if any(name.endswith(ext) for ext in (".webloc", ".url", ".desktop", ".lnk", ".link")):
        return None
    if "." not in name:
        name += ".bin"
    return name

def _download(session: requests.Session, url: str, dst: Path) -> bool:
    try:
        with session.get(url, stream=True, timeout=30, allow_redirects=True) as resp:
            resp.raise_for_status()
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "wb") as fh:
                for chunk in resp.iter_content(32_768):
                    fh.write(chunk)
        return True
    except requests.RequestException as exc:
        logger.warning("⚠️  Download failed for %s – %s", url, exc)
        return False

def _extract_meta_js_redirect(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
    if meta and (c := meta.get("content")) and "url=" in c.lower():
        url_part = c.split("url=", 1)[1].strip(" '")
        if url_part.lower().endswith(".pdf") or "pluginfile.php" in url_part:
            return url_part
    m = re.search(r"window\\.location(?:\\.href)?\\s*=\\s*['\"]([^'\"]+(?:pluginfile\\.php|\\.pdf)[^'\"]*)", html, re.I)
    return m.group(1) if m else None

def _dst_dir(metadata_path: str, suffix: str) -> Path:
    safe = suffix.lower().lstrip(".") or "other"
    return Path(metadata_path).with_name(f"files_{safe}")

# ---------------------------------------------------------------------------
# main crawler
# ---------------------------------------------------------------------------

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
    seen_urls: set[str] = set()

    for idx, grid in enumerate(grids, 1):
        try:
            try:
                a_tag = grid.find_element(By.XPATH,
                    ".//a[contains(@href,'/mod/resource/view.php') or contains(@href,'/mod/folder/view.php') or contains(@href,'/mod/url/view.php')]")
                view_url = a_tag.get_attribute("href")
                if not view_url or view_url in seen_urls:
                    continue
                seen_urls.add(view_url)
                title = a_tag.text.replace("\nDatei", "").replace("\nLink/URL", "").strip()
                res = session.get(view_url, stream=True, timeout=20, allow_redirects=True)
                res.raise_for_status()
            except NoSuchElementException:
                view_url = driver.current_url
                title = f"{course_id}_{idx:03d}"
                res = None

            if res is not None:
                final_url = res.url
                ctype = res.headers.get("Content-Type", "")

                if (not ctype.startswith("text/html") and ("application/" in ctype or final_url.lower().endswith(".pdf"))):
                    orig = _safe_filename(final_url)
                    if orig:
                        dst = _dst_dir(metadata_path, Path(orig).suffix) / f"{course_id}_{idx:03d}_document{Path(orig).suffix or '.bin'}"
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

                if "/mod/url/view.php" in view_url and "redirect=1" not in view_url:
                    redir_url = view_url + ("&" if "?" in view_url else "?") + "redirect=1"
                    try:
                        r2 = session.get(redir_url, stream=True, timeout=20, allow_redirects=True)
                        r2.raise_for_status()
                        if (not r2.headers.get("Content-Type", "").startswith("text/html") and
                            ("application/" in r2.headers.get("Content-Type", "") or r2.url.lower().endswith(".pdf"))):
                            orig = _safe_filename(r2.url)
                            if orig:
                                dst = _dst_dir(metadata_path, Path(orig).suffix) / f"{course_id}_{idx:03d}_document{Path(orig).suffix or '.bin'}"
                                if _download(session, r2.url, dst):
                                    logger.info("✅ Saved %s", dst)
                                    downloads.append({
                                        "title": title,
                                        "moodle_url": view_url,
                                        "download_url": r2.url,
                                        "saved_filename": dst.name,
                                        "saved_path": str(dst),
                                    })
                                    continue
                    except requests.RequestException:
                        pass

                html = res.text if res else grid.get_attribute("innerHTML")
            else:
                html = grid.get_attribute("innerHTML")

            soup = BeautifulSoup(html, "html.parser")
            links = soup.select("a[href*='pluginfile.php'], a[href$='.pdf']")
            if not links:
                redirect = _extract_meta_js_redirect(html)
                if redirect:
                    links = [BeautifulSoup(f'<a href="{redirect}"></a>', "html.parser").a]

            if not links:
                logger.warning("⚠️  No PDF/pluginfile links found in %s", view_url)
                continue

            def _nearest_folder(anchor) -> str:
                span = anchor.find_previous(lambda t: t.name == "span" and "fp-filename" in t.get("class", []) and not t.find("a"))
                return span.get_text(strip=True) if span else ""

            for subidx, link in enumerate(links, 1):
                dl_url = link["href"]
                orig = _safe_filename(dl_url)
                if orig is None or orig.lower().endswith((".zip", ".tar", ".gz", ".tgz", ".tar.gz")):
                    continue

                file_title = link.get_text(strip=True) or Path(orig).name
                folder_name = _nearest_folder(link)

                dst = _dst_dir(metadata_path, Path(orig).suffix) / f"{course_id}_{idx:03d}_{subidx:02d}_document{Path(orig).suffix or '.bin'}"
                if _download(session, dl_url, dst):
                    logger.info("✅ Saved %s", dst)
                    downloads.append({
                        "title": file_title,
                        "folder": folder_name,
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