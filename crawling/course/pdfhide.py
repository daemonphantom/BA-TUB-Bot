import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from ..data_storage import save_binary_file
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

def get_course_id_from_url(url):
    """
    Extract the course id from a course URL.
    Assumes the URL includes a query parameter such as ?id=12345.
    """
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query)
    return query_params.get("id", ["unknown"])[0]

def crawl(driver, pdf_folder):
    """
    Crawl PDFs from the course page.
    
    Process:
      1. Extract the course id from the current URL.
      2. Locate all activity grids that contain the PDF icon (with a specific 'src').
      3. For each grid:
         - Get the resource URL.
         - Open the resource page in a new tab.
         - If the resource page is directly a PDF (URL ends with .pdf), use that.
           Otherwise, wait until a valid PDF link appears.
         - Extract the PDF URL.
         - Retrieve the session cookies from Selenium and pass them to requests.get() so that the file is downloaded authenticated.
         - Download the PDF file and save it with the format: "<course_id>_<counter>_course_pdf.pdf"
         - Record metadata of the download.
    
    :param driver: Selenium WebDriver instance (already logged in and on the course page).
    :param pdf_folder: Folder path where the PDFs will be saved.
    :return: A list of metadata dictionaries for each downloaded PDF.
    """
    # Ensure pdf_folder is a string.
    pdf_folder = str(pdf_folder)
    
    # Extract the course id from the current page URL.
    course_url = driver.current_url
    course_id = get_course_id_from_url(course_url)
    print(f"Extracted course id: {course_id}")
    
    # Define the PDF icon src as observed on the site.
    pdf_icon_src = "https://isis.tu-berlin.de/theme/image.php/nephthys/core/1744140965/f/pdf?filtericon=1"
    
    # Find activity grids that have the PDF icon.
    activity_grids_with_pdf = driver.find_elements(
        By.CSS_SELECTOR, f".activity-grid:has([src='{pdf_icon_src}'])"
    )
    print(f"Found {len(activity_grids_with_pdf)} PDF activity grids.")
    
    metadata_list = []
    pdf_counter = 1
    main_tab = driver.window_handles[0]
    
    for grid in activity_grids_with_pdf:
        # Always return to the main tab before processing the next grid.
        driver.switch_to.window(main_tab)
        
        # Locate the resource link within the activity grid.
        url_elem = grid.find_element(By.CSS_SELECTOR, "a[href^='https://isis.tu-berlin.de/mod']")
        resource_url = url_elem.get_attribute("href")
    
        # Open the resource page in a new tab.
        driver.execute_script("window.open('about:blank', '_blank');")
        tabs = driver.window_handles
        driver.switch_to.window(tabs[-1])
        driver.get(resource_url)
        time.sleep(2)  # Allow time for the page to load or redirect.
    
        # Check if the page has already redirected directly to a PDF.
        current_url = driver.current_url
        if current_url.lower().endswith('.pdf'):
            absolute_pdf_url = current_url
            link_text = "Direct PDF Redirect"
            print(f"Detected PDF via URL redirect: {absolute_pdf_url}")
        else:
            # Wait until a valid PDF link appears in the resource page.
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: any(
                        (link.get_attribute("href") and 
                         ".pdf" in link.get_attribute("href").lower() and 
                         link.get_attribute("href").lower() != "about:blank")
                        for link in d.find_elements(By.CSS_SELECTOR, "a[href*='.pdf']")
                    )
                )
            except Exception as e:
                print(f"Timed out waiting for a valid PDF link on resource page: {resource_url}. Error: {e}")
                driver.close()
                driver.switch_to.window(main_tab)
                continue
            
            # Parse the resource page.
            resource_soup = BeautifulSoup(driver.page_source, "html.parser")
            pdf_link = resource_soup.find("a", href=lambda x: x and ".pdf" in x.lower() and x.lower() != "about:blank")
            if not pdf_link:
                pdf_embed = resource_soup.find("embed", type="application/pdf")
                if pdf_embed and pdf_embed.get("src"):
                    pdf_link = pdf_embed
            if not pdf_link:
                print(f"⚠️ No direct PDF link found on resource page: {resource_url}")
                driver.close()
                driver.switch_to.window(main_tab)
                continue
            
            if pdf_link.name == "embed":
                absolute_pdf_url = urljoin(resource_url, pdf_link.get("src"))
                link_text = "PDF Embedded Resource"
            else:
                absolute_pdf_url = urljoin(resource_url, pdf_link.get("href"))
                link_text = pdf_link.get_text(strip=True) or "PDF Resource"
    
        # Check that we have a valid URL.
        if not absolute_pdf_url or absolute_pdf_url.lower().startswith("about:blank"):
            print(f"⚠️ Skipping PDF download: invalid URL obtained ({absolute_pdf_url})")
            driver.close()
            driver.switch_to.window(main_tab)
            continue
        
        # Get authentication cookies from Selenium.
        selenium_cookies = driver.get_cookies()
        cookies = {cookie['name']: cookie['value'] for cookie in selenium_cookies}
        
        # Construct a new filename using the course id and an iterator.
        new_filename = f"{course_id}_{pdf_counter:02d}_course_pdf.pdf"
        file_path = os.path.join(pdf_folder, new_filename)
        
        try:
            print(f"⬇️ Downloading PDF from: {absolute_pdf_url}")
            response = requests.get(absolute_pdf_url, timeout=30, cookies=cookies)
            if response.status_code == 200:
                save_binary_file(response.content, file_path)
                print(f"✅ Saved PDF as: {file_path}")
            else:
                print(f"❌ Error downloading PDF: HTTP {response.status_code} - {absolute_pdf_url}")
                driver.close()
                driver.switch_to.window(main_tab)
                continue
        except Exception as e:
            print(f"❌ Exception downloading PDF from {absolute_pdf_url}: {e}")
            driver.close()
            driver.switch_to.window(main_tab)
            continue
        
        metadata = {
            "title": link_text,
            "original_url": absolute_pdf_url,
            "saved_filename": new_filename,
            "saved_filepath": file_path
        }
        metadata_list.append(metadata)
        pdf_counter += 1
        
        # Close the resource tab and switch back to the main tab.
        driver.close()
        driver.switch_to.window(main_tab)
    
    return metadata_list
