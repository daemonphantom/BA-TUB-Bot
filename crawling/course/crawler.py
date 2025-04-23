import os
from pathlib import Path
from ..navigator import open_course_by_id
from ..data_storage import init_course_dir, save_json
# Import all content-type crawler modules
from . import quiz, forum, group_building, links, pdf, videos, questionnaire
from ..utils import get_logger

logger = get_logger(__name__)


def crawl_course(driver, course_id: str):
    """
    Crawl all relevant data for a single course.
    Each module must implement a crawl() function.
    For the PDF module, we pass the destination folder as an extra argument.
    """
    logger.info(f"📘 Crawling course: {course_id}")

    # Step 2: Initialize the course folder structure
    course_path = init_course_dir(course_id)

    enabled_modules = ["forums", "pdf"]  # Adjust as needed

    # Step 3: Set up a mapping of each content type to its crawler module or a lambda adapter.
    # Here, the pdf crawler expects an extra argument, so we wrap it in a lambda.
    crawler_map = {}

    if "forums" in enabled_modules:
        crawler_map["forums"] = lambda driver: forum.crawl(driver, course_path / "forums")

    if "quizzes" in enabled_modules:
        crawler_map["quizzes"] = quiz

    if "questionnaire" in enabled_modules:
        crawler_map["questionnaire"] = questionnaire

    if "groups" in enabled_modules:
        crawler_map["groups"] = group_building

    if "links" in enabled_modules:
        crawler_map["links"] = links

    if "pdf" in enabled_modules:
        crawler_map["pdf"] = lambda driver: pdf.crawl(driver, course_path / "pdf")

    if "videos" in enabled_modules:
        crawler_map["videos"] = lambda driver: videos.crawl(driver, course_path / "videos")



    # Step 4: Iterate through each content type, crawl, and save the results.
    for section, module in crawler_map.items():
        try:
            logger.info(f"🔍 Crawling: {section}...")
            open_course_by_id(driver, course_id) # Navigate to course page
            # For pdf, the crawler is a lambda that already passes the folder.
            data = module.crawl(driver) if not callable(module) or module.__name__ != "<lambda>" else module(driver)
            # Only save if data is not empty
            if data:
                save_path = course_path / section / f"{section}.json"
                save_json(data, save_path)
                logger.info(f"✅ Saved {section} data to {save_path}.")
            else:
                logger.warning(f"⚠️ No data found for {section}.")
        except Exception as e:
            logger.error(f"❌ Error while crawling {section}: {e}")

    logger.info(f"🏁 Finished crawling course {course_id}")








# (Keep your crawler.py definitions above this block)

if __name__ == '__main__':
    import os
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from crawling.login import login  # Assumes login.py is implemented and working
    from dotenv import load_dotenv

    load_dotenv()  # Load credentials from your .env file

    # Setup Chrome options (remove headless if you want to see the browser in action)
    chrome_options = Options()
    # Uncomment the next line if you want headless mode
    #chrome_options.add_argument("--headless")

    # Initialize the driver
    driver = webdriver.Chrome(options=chrome_options)

    try:
        # Login: ensure your TUB_USERNAME and TUB_PASSWORD are set in your .env
        username = os.getenv('TUB_USERNAME')
        password = os.getenv('TUB_PASSWORD')
        login(driver, username, password)

        # Specify a test course ID that you know exists (modify accordingly)
        test_course_id = '41554'  # Replace with an actual course ID from your crawl_this_course_id.json

        # Now run the crawler
        from ..course.crawler import crawl_course
        crawl_course(driver, test_course_id)

    except Exception as e:
        logger.error(f"An error occurred during the test run: {e}")
    finally:
        driver.quit()
