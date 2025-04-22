import os, re, json, logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC



import time

# Configure logging (for development you can set level to DEBUG; adjust as needed for production)
logging.basicConfig(
    level=logging.DEBUG,  # Change to INFO or WARNING in production
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "https://isis.tu-berlin.de"

def slugify(name: str) -> str:
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss"
    }
    for orig, repl in replacements.items():
        name = name.replace(orig, repl).replace(orig.upper(), repl.capitalize())
    name = name.lower()
    name = name.replace(" ", "_")
    name = re.sub(r"[^a-z0-9_]", "", name)  # Keep only alphanum + underscore
    return name


def get_forums_on_course_page(driver, course_id):
    """
    Step 1: Load forum index and extract all forum sections (Ankündigungen, Forum, etc.)
    """
    forum_index_url = f"{BASE_URL}/mod/forum/index.php?id={course_id}"
    driver.get(forum_index_url)
    
    try:
        # Wait up to 4 seconds for the forum table to appear.
        WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table.generaltable"))
        )
    except Exception as e:
        print("⚠️ Forum table not found.", e)
        return []
    
    soup = BeautifulSoup(driver.page_source, "html.parser")

    forum_list = []
    table = soup.find("table", class_="generaltable")
    if not table:
        logger.warning("⚠️ Forum table not found.")
        return []

    for row in table.select("tbody tr"):
        try:
            cells = row.find_all("td")
            link = cells[0].find("a")
            forum_url = urljoin(forum_index_url, link.get("href"))
            forum_id = parse_qs(urlparse(forum_url).query).get("f", [""])[0]
            forum_list.append({
                "forum_name": link.text.strip(),
                "forum_url": forum_url,
                "forum_id": forum_id
            })
        except Exception as e:
            logger.warning(f"⚠️ Skipping forum row: {e}")
            continue
    return forum_list


def get_discussion_links(driver, forum_url):
    """
    Step 2: Open a specific forum page and extract all top-level thread links (discuss.php?d=...).
    Filters out timestamp-only links (e.g. 'Do., 17. Okt. 2024') and avoids duplicates.
    """
    driver.get(forum_url)
    
    try:
        # Wait up to 4 seconds for a discussion link to appear.
        WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='discuss.php?d=']"))
        )
    except Exception as e:
        print("⚠️ Discussion links not found.", e)
        return []
    
    soup = BeautifulSoup(driver.page_source, "html.parser")

    threads = {}
    for link in soup.select("a[href*='discuss.php?d=']"):
        href = link.get("href")
        title = link.get("title") or link.text.strip()

        parsed_url = urlparse(href)
        query = parse_qs(parsed_url.query)
        discussion_id = query.get("d", [None])[0]
        parent = query.get("parent", [None])[0]

        # Skip reply links (they include &parent=...) or incomplete ones
        if not discussion_id or parent:
            continue

        # Deduplicate by discussion ID
        if discussion_id not in threads:
            full_url = urljoin(BASE_URL, f"/mod/forum/discuss.php?d={discussion_id}")
            threads[discussion_id] = {
                "title": title,
                "url": full_url
            }
    return list(threads.values())


def parse_discussion(driver, discussion_url):
    """
    Step 3: Parse a full thread page, extracting all post metadata.
    """
    driver.get(discussion_url)

    try:
        # Wait up to 4 seconds for at least one post to be loaded.
        WebDriverWait(driver, 4).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.forumpost"))
        )
    except Exception as e:
        print("⚠️ No posts found in the discussion.", e)
        return []
    
    soup = BeautifulSoup(driver.page_source, "html.parser")
    posts = soup.find_all("div", class_="forumpost")
    post_data = []
    for post in posts:
        try:
            post_id = post.get("data-post-id", "unknown")
            header = post.find("header")
            subject = header.find("h3").text.strip() if header and header.find("h3") else "No subject"
            author = header.find("a").text.strip() if header and header.find("a") else "Unknown"
            datetime_val = header.find("time")["datetime"] if header and header.find("time") else "Unknown"
            
            content_div = post.find("div", class_="post-content-container")
            # Convert <a> tags to "text (URL)"
            for a in content_div.find_all("a"):
                text = a.get_text()
                href = a.get("href")
                if href:
                    a.replace_with(f"{text} ({href})")

            content = content_div.get_text(" ", strip=True)

            # Get response link (structure)
            response_anchor = post.find("a", title=lambda t: t and "Ursprungsbeitrag" in t)
            if response_anchor:
                raw_response_to = response_anchor["href"].split("#")[-1]
                response_to = raw_response_to.replace("p", "") if raw_response_to.startswith("p") else raw_response_to  # reply_to IDs start with "p", thread IDs don't; remove "p"
                is_reply = True
                is_thread_root = False
            else:
                response_to = None
                is_reply = False
                is_thread_root = True

            post_data.append({
                "post_id": post_id,
                "subject": subject,
                "author": author,
                "datetime": datetime_val,
                "content": content,
                "response_to": response_to,
                "is_reply": is_reply,
                "is_thread_root": is_thread_root,
                "permalink": f"{discussion_url}#p{post_id}"
            })
        except Exception as e:
            logger.warning(f"⚠️ Error parsing post: {e}")
            continue
    return post_data


def crawl(driver, forum_folder):
    """
    This is the crawl() entry point for forum.py.
    """
    os.makedirs(forum_folder, exist_ok=True)
    course_url = driver.current_url
    course_id = parse_qs(urlparse(course_url).query).get("id", ["unknown"])[0]
    # Check for invalid or unwanted course IDs
    if course_id in ["unknown", "1"]:
        logger.error(f"⚠️ Invalid or unwanted course ID detected: {course_id}. Aborting crawl.")
        return []
    
    logger.info(f"📚 Crawling forums for course ID: {course_id}")

    forums = get_forums_on_course_page(driver, course_id)
    summary = []

    for i, forum in enumerate(forums, start=1):
        logger.info(f"➡️ Crawling forum: {forum['forum_name']}")

        threads = get_discussion_links(driver, forum["forum_url"])
        forum_data = []

        for thread in threads:
            logger.info(f"   🧵 Thread: {thread['title']}")
            posts = parse_discussion(driver, thread["url"])
            forum_data.append({
                "thread_title": thread["title"],
                "thread_url": thread["url"],
                "posts": posts
            })

        # Save as JSON with new filename style
        safe_name = slugify(forum["forum_name"])
        forum_path = os.path.join(forum_folder, f"{course_id}_forum_{i:02d}_{safe_name}.json")
        with open(forum_path, "w", encoding="utf-8") as f:
            json.dump(forum_data, f, ensure_ascii=False, indent=2)

        summary.append({
            "forum_name": forum["forum_name"],
            "thread_count": len(threads),
            "saved_to": forum_path
        })
    return summary
