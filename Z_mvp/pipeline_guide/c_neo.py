from neo4j import GraphDatabase
from typing import Iterable
import numpy as np
from .a_load_forum_data import ForumPost


class GraphStore:
    """Handles Neo4j database operations"""

    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="password"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._setup_database()

    def close(self):
        self.driver.close()

    def _setup_database(self):
        """Create indexes and constraints"""
        with self.driver.session() as session:
            # Uniqueness
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Post) REQUIRE p.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE")
            # Helpful indexes
            session.run("CREATE INDEX IF NOT EXISTS FOR (p:Post) ON (p.thread_id)")
            session.run("CREATE INDEX IF NOT EXISTS FOR (p:Post) ON (p.post_datetime)")

            # OPTIONAL: native vector index (Neo4j 5.11+). Adjust dimensions to your model.
            # session.run(\"\"\"\n
            # CREATE VECTOR INDEX post_embedding IF NOT EXISTS FOR (p:Post) ON (p.embedding)
            # OPTIONS { indexConfig: { 'vector.dimensions': 512, 'vector.similarity_function': 'cosine' } }
            # \"\"\")

    def store_post(self, post: ForumPost, embedding: np.ndarray):
        emb_list = embedding.astype(float).tolist()

        with self.driver.session() as session:
            # Upsert Post node
            session.run(
                """
                MERGE (p:Post {id: $post_id})
                ON CREATE SET
                    p.content = $content,
                    p.subject = $subject,
                    p.thread_id = $thread_id,
                    p.thread_title = $thread_title,
                    p.thread_url = $thread_url,
                    p.author_name = $author,
                    p.post_datetime = $post_datetime,
                    p.permalink = $permalink,
                    p.is_reply = $is_reply,
                    p.is_thread_root = $is_thread_root,
                    p.has_attachments = $has_attachments,
                    p.course_id = $course_id,
                    p.course_name = $course_name,
                    p.course_semester = $course_semester,
                    p.course_faculty = $course_faculty,
                    p.crawl_datetime = $crawl_datetime,
                    p.embedding = $embedding
                ON MATCH SET
                    p.content = $content,
                    p.subject = $subject,
                    p.embedding = $embedding
                """,
                post_id=post.post_id,
                content=post.content,
                subject=post.subject,
                thread_id=post.thread_id,
                thread_title=post.thread_title,
                thread_url=post.thread_url,
                author=post.author,
                post_datetime=post.post_datetime,
                permalink=post.permalink,
                is_reply=post.is_reply,
                is_thread_root=post.is_thread_root,
                has_attachments=post.has_attachments,
                course_id=post.course_id,
                course_name=post.course_name,
                course_semester=post.course_semester,
                course_faculty=post.course_faculty,
                crawl_datetime=post.crawl_datetime,
                embedding=emb_list,
            )

            # Upsert Author and authored relation
            session.run(
                """
                MERGE (a:Author {name: $author})
                WITH a
                MATCH (p:Post {id: $post_id})
                MERGE (a)-[:AUTHORED]->(p)
                """,
                author=post.author,
                post_id=post.post_id,
            )

    def link_replies(self, posts: Iterable[ForumPost]):
        """Create reply edges after all posts are inserted"""
        with self.driver.session() as session:
            for post in posts:
                if post.is_reply and post.response_to:
                    session.run(
                        """
                        MATCH (reply:Post {id: $reply_id})
                        MATCH (orig:Post {id: $orig_id})
                        MERGE (reply)-[:REPLIES_TO]->(orig)
                        """,
                        reply_id=post.post_id,
                        orig_id=post.response_to,
                    )
