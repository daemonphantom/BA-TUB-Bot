import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from ..data_storage import save_binary_file
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from ..utils import get_course_id_from_url, get_logger

logger = get_logger(__name__)

def extract_pdf_url(driver, resource_url):
    """Open resource page and extract actual PDF URL (handles redirect or embedded link)."""
    driver.get(resource_url)
    time.sleep(2)
    current_url = driver.current_url

    # Case 1: Direct redirect to PDF
    if current_url.lower().endswith('.pdf'):
        logger.info(f"Detected PDF via URL redirect: {current_url}")
        return current_url, "Direct PDF Redirect"

    # Case 2: Look for PDF link in HTML (e.g. external resource page)
    try:
        WebDriverWait(driver, 10).until(
            lambda d: any(
                (link.get_attribute("href") and ".pdf" in link.get_attribute("href").lower())
                for link in d.find_elements(By.CSS_SELECTOR, "a[href*='.pdf']")
            )
        )
    except Exception as e:
        logger.warning(f"Timed out waiting for PDF link in: {resource_url}. Error: {e}")
        return None, None

    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Moodle external PDF workaround
    workaround = soup.find("div", class_="urlworkaround")
    if workaround:
        link = workaround.find("a", href=True)
        if link and link["href"].endswith(".pdf"):
            return link["href"], link.text.strip() or "External PDF Resource"

    # Regular link or embed
    pdf_link = soup.find("a", href=lambda x: x and ".pdf" in x.lower())
    if pdf_link:
        return urljoin(resource_url, pdf_link["href"]), pdf_link.text.strip() or "PDF Resource"

    embed = soup.find("embed", type="application/pdf")
    if embed and embed.get("src"):
        return urljoin(resource_url, embed["src"]), "PDF Embedded Resource"

    logger.warning(f"⚠️ No PDF found on: {resource_url}")
    return None, None

def crawl(driver, pdf_folder):
    pdf_folder = str(pdf_folder)
    course_id = get_course_id_from_url(driver.current_url)
    metadata_list = []
    pdf_counter = 1

    # 🔍 Step 1: Find activity grids with PDF icon
    activity_grids = driver.find_elements(By.CSS_SELECTOR, ".activity-grid:has([src*='/f/pdf?filtericon=1'])")
    logger.info(f"Found {len(activity_grids)} PDF activity grids.")

    main_tab = driver.window_handles[0]

    for grid in activity_grids:
        driver.switch_to.window(main_tab)
        url_elem = grid.find_element(By.CSS_SELECTOR, "a[href^='https://isis.tu-berlin.de/mod']")
        resource_url = url_elem.get_attribute("href")

        driver.execute_script("window.open('about:blank', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])

        # 📥 Step 2: Extract PDF URL from resource page
        absolute_pdf_url, link_text = extract_pdf_url(driver, resource_url)

        if not absolute_pdf_url or absolute_pdf_url.lower().startswith("about:blank"):
            driver.close()
            continue

        # 📥 Step 3: Download PDF using Selenium cookies
        selenium_cookies = driver.get_cookies()
        cookies = {cookie['name']: cookie['value'] for cookie in selenium_cookies}

        new_filename = f"{course_id}_{pdf_counter:02d}_course_pdf.pdf"
        file_path = os.path.join(pdf_folder, new_filename)

        try:
            logger.info(f"⬇️ Downloading PDF from: {absolute_pdf_url}")
            response = requests.get(absolute_pdf_url, timeout=30, cookies=cookies)
            if response.status_code == 200 and response.headers.get("Content-Type", "").startswith("application/pdf"):
                save_binary_file(response.content, file_path)
                logger.info(f"✅ Saved PDF as: {file_path}")
            else:
                logger.warning(f"❌ Skipped non-PDF content. Content-Type: {response.headers.get('Content-Type')} | URL: {absolute_pdf_url}")
                driver.close()
                continue
        except Exception as e:
            logger.error(f"❌ Exception downloading PDF from {absolute_pdf_url}: {e}")
            driver.close()
            continue

        metadata_list.append({
            "title": link_text,
            "original_url": absolute_pdf_url,
            "saved_filename": new_filename,
            "saved_filepath": file_path
        })
        pdf_counter += 1

        driver.close()

    driver.switch_to.window(main_tab)
    return metadata_list
