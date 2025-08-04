from sentence_transformers import SentenceTransformer
import json
import os
from neo4j import GraphDatabase

model = SentenceTransformer("jinaai/jina-embeddings-v2-base-de")

json_path = "B_data/course_40280/forums/40280_forum_02_studierendenforum__2025-08-03T00-26+00-00.json"

with open(json_path, "r", encoding="utf-8") as f:
    thread = json.load(f)

chunks = thread["posts"]


model = SentenceTransformer("jinaai/jina-embeddings-v2-base-de")
for post in chunks:
    post["embedding"] = model.encode(post["content"]).tolist()

from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "your_password"))

def insert_post(tx, post):
    meta = post["metadata"]
    course = meta["course"]

    tx.run("""
        MERGE (c:Course {id: $course_id})
          ON CREATE SET c.name = $course_name, c.semester = $semester, c.faculty = $faculty

        MERGE (t:ForumThread {id: $thread_id})
          ON CREATE SET t.title = $thread_title, t.url = $thread_url

        MERGE (p:Chunk {id: $post_id})
          SET p.text = $content,
              p.chunk_type = $chunk_type,
              p.author = $author,
              p.post_datetime = datetime($post_datetime),
              p.crawl_datetime = datetime($crawl_datetime),
              p.course_id = $course_id,
              p.thread_id = $thread_id,
              p.subject = $subject,
              p.embedding = $embedding

        MERGE (p)-[:BELONGS_TO]->(c)
        MERGE (p)-[:IN_THREAD]->(t)
    """,
    course_id=course["id"],
    course_name=course["name"],
    semester=course["semester"],
    faculty=course["faculty"],
    thread_id=meta["thread_id"],
    thread_title=post.get("thread_title", "Unknown"),
    thread_url=post.get("thread_url", "Unknown"),
    post_id=meta["post_id"],
    content=post["content"],
    chunk_type=post["chunk_type"],
    author=meta["author"],
    post_datetime=meta["post_datetime"],
    crawl_datetime=meta["crawl_datetime"],
    subject=meta["subject"],
    embedding=post["embedding"]
)
