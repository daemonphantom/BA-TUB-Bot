from ..course.forum import get_forums_on_course_page

forums = get_forums_on_course_page(driver, course_id="30422")

for forum in forums:
    print(f"{forum['forum_name']} ({forum['thread_count']} threads): {forum['forum_url']}")
