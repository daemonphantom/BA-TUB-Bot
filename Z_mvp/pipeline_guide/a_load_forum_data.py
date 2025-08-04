import json
from dataclasses import dataclass
from typing import Dict, Optional

@dataclass
class ForumPost:
    thread_title: str
    thread_url: str
    # posts:
    chunk_type: str
    content: str
    #   metadata:
    #       course:
    course_id: str
    course_name: str
    course_semester: str
    course_faculty: str

    post_id: str
    thread_id: str
    subject: str
    author: str
    post_datetime: str
    permalink: str
    is_reply: bool
    is_thread_root: bool
    has_attachments: bool
    # attachments:
    attachments: Optional[list[str]]
    local_attachments: Optional[list[str]]

    #links:
    links: Optional[list[Dict[str, str]]]

    crawl_datetime: str
    response_to: Optional[str] = None

    def get_text_for_embedding(self) -> str:
        return self.content.strip()

def load_forum_data(json_file: str) -> list[ForumPost]:
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    posts = []
    for thread in data:
        thread_title = thread["thread_title"]
        thread_url = thread["thread_url"]
        for post_data in thread["posts"]:
            metadata = post_data["metadata"]
            course = metadata["course"]
            post = ForumPost(
                thread_title=thread_title,
                thread_url=thread_url,
                chunk_type=post_data["chunk_type"],
                content=post_data["content"],
                course_id=course["id"],
                course_name=course["name"],
                course_semester=course["semester"],
                course_faculty=course.get("faculty"),
                post_id=metadata["post_id"],
                thread_id=metadata["thread_id"],
                subject=metadata["subject"],
                author=metadata["author"],
                post_datetime=metadata["post_datetime"],
                permalink=metadata["permalink"],
                is_reply=metadata["is_reply"],
                is_thread_root=metadata["is_thread_root"],
                has_attachments=metadata["has_attachments"],
                #attachments=metadata.get("attachments", []),
                #local_attachments=metadata.get("local_attachments", []),
                #links=metadata.get("links", []),
                crawl_datetime=metadata["crawl_datetime"],
                response_to=metadata.get("response_to")
            )
            posts.append(post)

    return posts


if __name__ == "__main__":
    posts = load_forum_data('./B_data/course_40280/forums/40280_forum_02_studierendenforum__2025-08-03T00-26+00-00.json')
    #posts = load_forum_data('./B_data/course_40280/forums/40280_forum_01_ankuendigungen__2025-08-03T00-24+00-00.json')

    print(f"✅ Loaded {len(posts)} posts")
    print(f"✅ Response_to: {posts[3].response_to}")
