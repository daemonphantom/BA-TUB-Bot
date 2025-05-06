import os
from pathlib import Path
from ..navigator import open_course_by_id
from ..data_storage import init_course_dir, save_json
# Import all content-type crawler modules
from . import image, quiz, forum, links, videos, questionnaire, mainpage, subpages, resources, document
from ..utils import get_logger

logger = get_logger(__name__)


def crawl_course(driver, course_id: str):
    """
    Crawl all relevant data for a single course.
    Each module must implement a crawl() function.
    For the PDF module, we pass the destination folder as an extra argument.
    """
    enabled_modules = ["forums"]  # Adjust as needed                                                                       !!!!!!!!!!!!!!!!!!!!!!!!


    logger.info(f"📘 Crawling course: {course_id}")

    # Step 2: Initialize the course folder structure
    course_path = init_course_dir(course_id)


    # Step 3: Set up a mapping of each content type to its crawler module or a lambda adapter.
    # Here, the pdf crawler expects an extra argument, so we wrap it in a lambda.
    crawler_map = {
        "forums":       (forum.crawl,        course_path / "forums"),
        #"quizzes":      (quiz.crawl,         course_path / "quizzes"),
        #"questionnaire":(questionnaire.crawl,course_path / "questionnaire"),
        #"groups":       (group_building.crawl,course_path / "groups"),
        "links":        (links.crawl,        course_path / "links" / "links.json"),
        "videos":       (videos.crawl,       course_path / "videos"),
        "mainpage":     (mainpage.crawl,     course_path / "mainpage" / "mainpage.json"),
        "subpages":     (subpages.crawl,     course_path / "subpages" / "subpages.json"),
        "image":       (image.crawl,        course_path / "image" / "image_metadata.json"),
        "resources": (resources.crawl, course_path / "resources" / "resources.json"),
        "document": (document.crawl, course_path / "document" / "documents.json")
    }


    # Step 4: Iterate through each content type, crawl, and save the results.
    for section in enabled_modules:
        if section not in crawler_map:
            continue

        crawl_fn, output_path = crawler_map[section]

        try:
            logger.info(f"🔍 Crawling: {section}...")
            open_course_by_id(driver, course_id)
            data = crawl_fn(driver, output_path)

            if data:
                save_path = output_path if output_path.suffix == ".json" else output_path / f"{section}.json"
                save_json(data, save_path)
                logger.info(f"✅ Saved {section} data to {save_path}")
            else:
                logger.warning(f"⚠️ No data found for {section}.")
        except Exception as e:
            logger.error(f"❌ Error while crawling {section}: {e}")


    logger.info(f"🏁 Finished crawling course {course_id}")








# (Keep your crawler.py definitions above this block)

if __name__ == '__main__':
    import os
    import json
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from crawling.login import login
    from dotenv import load_dotenv

    load_dotenv()

    chrome_options = Options()
    #chrome_options.add_argument("--headless")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        username = os.getenv('TUB_USERNAME')
        password = os.getenv('TUB_PASSWORD')
        login(driver, username, password)

        # Simple relative path without extra packages
        with open("./crawling/course_ID_saved.json", "r", encoding="utf-8") as f:
            course_data = json.load(f)
        test_course_ids = [course["id"] for course in course_data]

        from ..course.crawler import crawl_course

        for course_id in test_course_ids:
            crawl_course(driver, course_id)

    except Exception as e:
        logger.error(f"An error occurred during the test run: {e}")
    finally:
        driver.quit()

