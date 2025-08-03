import os
from pathlib import Path
from .navigator import open_course_by_id
from .crawler_data_storage import init_course_dir, save_json

from . import crawler_document, crawler_feedback, crawler_forum, crawler_glossaries, crawler_image, crawler_links, crawler_mainpage, crawler_questionnaire, crawler_quiz, crawler_resources, crawler_subpages, crawler_videos
from .utils.utils import get_logger

logger = get_logger(__name__)

def crawl_course(driver, course_id: str):
    """
    Crawl all relevant data for a single course.
    """
    # Enabled Modules. Adjust as needed:
    enabled_modules = ["forums"]
    #"glossaries", "image", "quiz", "forums", "links", "videos", "mainpage", "subpages", "resources", "document"

    logger.info(f"📘 Crawling course: {course_id}")

    # Step 2: Initialize the course folder structure
    course_path = init_course_dir(course_id)


    # Step 3: Set up a mapping of each content type to its crawler module or a lambda adapter.
    # Here, the pdf crawler expects an extra argument, so we wrap it in a lambda.
    crawler_map = {
        "quiz":      (crawler_quiz.crawl,         course_path / "quizzes"),
        "forums": (lambda driver, path: crawler_forum.crawl(driver, path, course_metadata), course_path / "forums"),
        "glossaries":   (crawler_glossaries.crawl, course_path / "glossaries"),
        "links":        (crawler_links.crawl,        course_path / "links" / "links.json"),
        "videos":       (crawler_videos.crawl,       course_path / "videos"),
        "mainpage":     (crawler_mainpage.crawl,     course_path / "mainpage" / "mainpage.json"),
        "subpages":     (crawler_subpages.crawl,     course_path / "subpages" / "subpages.json"),
        "image":        (crawler_image.crawl,        course_path / "image" / "image_metadata.json"),
        "resources":    (crawler_resources.crawl, course_path / "resources" / "resources.json"),
        "document":     (crawler_document.crawl, course_path / "document" / "documents.json")
        #"groups":       (group_building.crawl,course_path / "groups"),
        #"feedback":   (feedback.crawl, course_path / "feedback"),
        #"questionnaire":(questionnaire.crawl,course_path / "questionnaire"),
    }

    ##########
    # Load course metadata once
    COURSE_METADATA_PATH = os.path.join("A_pipeline", "a_crawling", "course_ids", "all_courses.json")
    with open(COURSE_METADATA_PATH, "r", encoding="utf-8") as f:
        all_courses = json.load(f)
    course_lookup = {str(c["id"]): c for c in all_courses}
    course_metadata = course_lookup.get(str(course_id), {
        "id": str(course_id),
        "name": "Unknown Course",
        "semester": "Unknown Semester",
        "faculty": "Unknown Faculty"
    })
    logger.info(f"📚 Using course metadata: {course_metadata}")

    # Step 4: Iterate through each content type, crawl, and save the results.
    for section in enabled_modules:
        if section not in crawler_map:
            continue

        crawl_fn, output_path = crawler_map[section]

        try:
            logger.info(f"🔍 Crawling: {section}...")
            open_course_by_id(driver, course_id)
            data = crawl_fn(driver, output_path)

            if output_path.suffix == ".json":
                if data:
                    save_json(data, output_path)
                    logger.info(f"✅ Saved {section} data to {output_path}")
                else:
                    logger.warning(f"⚠️ No data found for {section}.")
            else:
                logger.info(f"✅ Finished crawling {section}.")

        except Exception as e:
            logger.error(f"❌ Error while crawling {section}: {e}")


    logger.info(f"🏁 Finished crawling course {course_id}")


if __name__ == '__main__':
    import os
    import json
    from seleniumwire import webdriver
    from selenium.webdriver.chrome.options import Options
    from A_pipeline.a_crawling.login import login
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
        with open("./a_pipeline/a_crawling/course_ids/course_ID_saved.json", "r", encoding="utf-8") as f:
            course_data = json.load(f)
        test_course_ids = [course["id"] for course in course_data]

        for course_id in test_course_ids:
            crawl_course(driver, course_id)

    except Exception as e:
        logger.error(f"An error occurred during the test run: {e}")
    finally:
        driver.quit()

