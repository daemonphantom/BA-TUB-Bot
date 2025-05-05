"""resources_crawler_improved.py

* **Direct HTTP resolution** – we request the `view.php` page with the same
  session cookies; Moodle instantly sends an HTTP redirect (302 / 303) to the
  `pluginfile.php` asset.  We follow that redirect and stream the response to
  disk – *exactly* what the browser would have downloaded.

* **Cleaner grid detection** – avoid the `:has()` selector.  We
  first collect all `.activity-grid` elements and keep only those that contain
  an `<img>` with `/f/archive` in its `src`.

"""

from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import List
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from ..utils import get_course_id_from_url, get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

# Return the base filename of *url*.
# The Moodle `pluginfile.php` path often includes the original filename – we simply extract that part.
def _safe_filename_from_url(url: str) -> str:
    name = Path(unquote(urlparse(url).path)).name
    if "." not in name:
        name += ".bin"
    return name

def _stream_download(session: requests.Session, url: str, filepath: Path) -> bool:
    """Download *url* via *session* streaming straight to *filepath*."""
    try:
        resp = session.get(url, stream=True, timeout=20, allow_redirects=True)
        resp.raise_for_status()

        # Create parent directories once all good
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as fp:
            for chunk in resp.iter_content(chunk_size=32_768):
                fp.write(chunk)
        return True
    except (requests.Timeout, requests.RequestException) as exc:
        logger.warning("⚠️ Download failed for %s – %s", url, exc)
        return False


# ---------------------------------------------------------------------------
# Public crawler entry point
# ---------------------------------------------------------------------------

def crawl(driver, metadata_path: str) -> List[dict]:
    """Crawl the current course page for archive (`/f/archive`) resource grids.

    Parameters
    ----------
    driver : selenium.webdriver
        Authenticated driver, already inside a Moodle course.
    metadata_path : str
        JSON file where metadata should be written.

    Returns
    -------
    List[dict]
        One dict per successfully downloaded archive.
    """

    course_id = get_course_id_from_url(driver.current_url)
    logger.info("📦 Crawling archive resources for course %s", course_id)

    # ---------------------------------------------------------------------
    # 1) Locate activity grids whose *icon* contains '/f/archive'.
    # ---------------------------------------------------------------------
    candidate_grids = driver.find_elements(By.CSS_SELECTOR, ".activity-grid")
    archive_grids = [
        g for g in candidate_grids
        if g.find_elements(By.CSS_SELECTOR,
                        "img[src*='/f/archive'], img[src*='/f/sourcecode']")
    ]

    # ---------------------------------------------------------------------
    # 2) Prepare HTTP session with Selenium cookies & UA
    # ---------------------------------------------------------------------
    session = requests.Session()
    for c in driver.get_cookies():
        session.cookies.set(c["name"], c["value"])
    session.headers.update({"User-Agent": driver.execute_script("return navigator.userAgent;")})

    # ---------------------------------------------------------------------
    # 3) Iterate & download
    # ---------------------------------------------------------------------
    downloads: List[dict] = []
    processed_urls = set()

    for idx, grid in enumerate(archive_grids, start=1):
        try:
            # Get the <a> surrounding the icon (first ancestor anchor)
            a_tag = grid.find_element(By.XPATH, ".//a[contains(@href,'/mod/resource/view.php')]")
            moodle_url = a_tag.get_attribute("href")
            if not moodle_url or moodle_url in processed_urls:
                continue
            processed_urls.add(moodle_url)

            # Derive a clean title (Moodle appends “\nDatei” inside .instancename)
            try:
                title_span = a_tag.find_element(By.CSS_SELECTOR, ".instancename")
                # cut off everything after the last “\nDatei”
                title = title_span.text.rsplit("\nDatei", 1)[0].strip()
            except Exception:
                # fallback: use anchor text and strip the suffix if present
                title = a_tag.text.replace("\nDatei", "").strip()

            # 3a. Resolve the redirect → actual file
            logger.debug("Resolving %s", moodle_url)
            res = session.get(moodle_url, stream=True, timeout=20, allow_redirects=True)
            res.raise_for_status()

            # Final URL (after redirects) is res.url
            download_url = res.url
            if "pluginfile.php" not in download_url:
                logger.warning("Skipping non‑pluginfile resource %s", download_url)
                continue

            # 3b. Determine filename & save
            orig_filename = _safe_filename_from_url(download_url)
            # pick target directory: ZIPs -> files_zip, single code files -> files_single
            if grid.find_elements(By.CSS_SELECTOR, "img[src*='/f/archive']"):
                subfolder = "files_zip"        # bulk archives
            else:                              # '/f/sourcecode', '/f/markup', ...
                subfolder = "files_single"     # single‑file downloads
            save_dir = Path(metadata_path).with_name(subfolder)
            save_path = save_dir / f"{course_id}_{idx:03d}_{orig_filename}"

            # If we've already streamed the bytes (res.iter_content not yet
            # consumed) we can pass the open response to the helper.
            ok = False
            try:
                # Write already‑open response without extra request
                save_path.parent.mkdir(parents=True, exist_ok=True)
                with open(save_path, "wb") as fp:
                    for chunk in res.iter_content(chunk_size=32_768):
                        fp.write(chunk)
                ok = True
            except Exception as exc:
                logger.debug("Inline stream failed, retrying fresh – %s", exc)

            if not ok:  # fallback – fetch again (handles edge‑cases)
                ok = _stream_download(session, download_url, save_path)

            if ok:
                logger.info("✅ Downloaded %s", save_path)
                downloads.append(
                    {
                        "title": title,
                        "moodle_url": moodle_url,
                        "download_url": download_url,
                        "saved_filename": save_path.name,
                        "saved_path": str(save_path),
                    }
                )
        except (NoSuchElementException, requests.RequestException) as exc:
            logger.warning("⚠️ Could not process archive grid – %s", exc)
            continue

    # ---------------------------------------------------------------------
    # 4) Write metadata JSON
    # ---------------------------------------------------------------------
    Path(metadata_path).parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as fp:
        json.dump(downloads, fp, ensure_ascii=False, indent=2)

    logger.info("📝 Saved metadata for %d archive files to %s", len(downloads), metadata_path)
    return downloads
