import os
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from .data_storage import save_binary_file
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from .misc import get_course_id_from_url, get_logger

logger = get_logger(__name__)

def download_video_with_retries(url, cookies, timeout=60, max_retries=5):
    session = requests.Session()
    # Configure the retry strategy.
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=1,  # Wait 1, 2, 4... seconds between retries.
        status_forcelist=[502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    return session.get(url, timeout=timeout, cookies=cookies)



def crawl(driver, video_folder):
    """
    Crawl all videos from the course’s video service browse page.
    
    Process:
      1. From the main course page, extract the course id.
      2. Construct and navigate to the video browse page:
             https://isis.tu-berlin.de/mod/videoservice/view.php/course/<course_id>/browse
      3. On the browse page, iterate over the video rows.
      4. For each video row, extract visible metadata (title, video info, collection name, description)
         and the URL from the title link that leads to the video detail page.
      5. Open the detail page in a new tab, then attempt to locate a direct video download link; if none is present,
         retrieve the video element's src attribute.
      6. Retrieve authentication cookies from Selenium and use them to download the video with requests.
      7. Save the video with a standardized filename: "<course_id>_<counter>_course_video.mp4", and record metadata.
    
    :param driver: Selenium WebDriver instance, already logged in.
    :param video_folder: Folder path where video files should be saved.
    :return: List of metadata dictionaries for each downloaded video.
    """
    video_folder = str(video_folder)
    
    # Step 1: Extract course id from the current main course page URL.
    main_course_url = driver.current_url
    course_id = get_course_id_from_url(main_course_url)
    
    # Step 2: Construct the video browse page URL and navigate there.
    browse_url = f"https://isis.tu-berlin.de/mod/videoservice/view.php/course/{course_id}/browse"
    logger.info(f"Navigating to videos browse page: {browse_url}")
    driver.get(browse_url)
    time.sleep(2)  # Replace with WebDriverWait if needed.
    
    # Step 3: Locate all video rows on the browse page.
    # Adjust the selector according to your actual HTML structure.
    video_rows = driver.find_elements(By.CSS_SELECTOR, "div.col.align-self-center.p-b-1")
    logger.info(f"Found {len(video_rows)} video rows on the page.")
    
    metadata_list = []
    video_counter = 1
    main_tab = driver.window_handles[0]
    
    # Step 4: Process each video row.
    for row in video_rows:
        try:
            # Extract metadata from the row.
            title_elem = row.find_element(By.CSS_SELECTOR, "div.title a")
            title = title_elem.text.strip()
            detail_href = title_elem.get_attribute("href")
            
            # Other metadata fields.
            video_info = ""
            collection_name = ""
            description = ""
            try:
                video_info = row.find_element(By.CSS_SELECTOR, "div.video-info").text.strip()
            except Exception:
                pass
            try:
                collection_name = row.find_element(By.CSS_SELECTOR, "div.collection-name a").text.strip()
            except Exception:
                pass
            try:
                description = row.find_element(By.CSS_SELECTOR, "div.description").text.strip()
            except Exception:
                pass
            
            logger.info(f"Processing video: {title}")
            
            # Step 5: Open video detail page in a new tab.
            driver.switch_to.window(main_tab)
            driver.execute_script("window.open('about:blank', '_blank');")
            tabs = driver.window_handles
            driver.switch_to.window(tabs[-1])
            detail_url = urljoin(browse_url, detail_href)
            driver.get(detail_url)
            time.sleep(2)
            
            # Step 6: Try to locate a "Download Video" link.
            try:
                download_link_elem = driver.find_element(
                    By.XPATH, 
                    "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'video herunterladen')]"
                )
                video_download_url = download_link_elem.get_attribute("href")
                logger.info(f"Found download link: {video_download_url}")
            except Exception as e:
                logger.info("No download button found; attempting to extract video element src.")
                try:
                    video_elem = driver.find_element(By.CSS_SELECTOR, "video.vjs-tech[src*='.mp4']")
                    video_download_url = video_elem.get_attribute("src")
                    logger.info(f"Found video element src: {video_download_url}")
                except Exception as e:
                    logger.error(f"❌ Could not find a video download URL on page: {detail_url}")
                    driver.close()
                    driver.switch_to.window(main_tab)
                    continue
            
            # Ensure the video URL is absolute.
            video_download_url = urljoin(detail_url, video_download_url)
            
            # Step 7: Get cookies from Selenium for an authenticated download.
            selenium_cookies = driver.get_cookies()
            cookies = {cookie['name']: cookie['value'] for cookie in selenium_cookies}
            
            # Construct the new filename.
            new_filename = f"{course_id}_{video_counter:02d}_course_video.mp4"
            file_path = os.path.join(video_folder, new_filename)
            
            # Download the video.
            logger.info(f"⬇️ Downloading video from: {video_download_url}")
            response = download_video_with_retries(video_download_url, cookies, timeout=60, max_retries=5)
            if response.status_code == 200:
                save_binary_file(response.content, file_path)
                logger.info(f"✅ Saved video as: {file_path}")
            else:
                logger.error(f"❌ Error downloading video: HTTP {response.status_code} - {video_download_url}")
                driver.close()
                driver.switch_to.window(main_tab)
                continue

            
            # Create metadata dictionary.
            video_metadata = {
                "title": title,
                "detail_url": detail_url,
                "video_info": video_info,
                "collection_name": collection_name,
                "description": description,
                "download_url": video_download_url,
                "saved_filename": new_filename,
                "saved_filepath": file_path,
            }
            metadata_list.append(video_metadata)
            video_counter += 1
            
            # Close the detail tab and switch back to the main browse page tab.
            driver.close()
            driver.switch_to.window(main_tab)
            
        except Exception as e:
            logger.error(f"❌ Exception processing video row: {e}")
            # Ensure we return to the main tab.
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(main_tab)
            continue
    
    return metadata_list
