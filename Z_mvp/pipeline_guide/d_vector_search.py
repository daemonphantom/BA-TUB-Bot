from .c_neo import GraphStore
import numpy as np

class VectorSearch:
    def __init__(self, graph_store: GraphStore, dims: int = 512):
        self.graph = graph_store
        self.dims = dims
        self._create_vector_index()

    def _create_vector_index(self):
        with self.graph.driver.session() as session:
            session.run(f"""
                CREATE VECTOR INDEX post_embeddings IF NOT EXISTS
                FOR (p:Post) ON (p.embedding)
                OPTIONS {{
                    indexConfig: {{
                        `vector.dimensions`: {self.dims},
                        `vector.similarity_function`: 'cosine'
                    }}
                }}
            """)
        print(f"✅ Vector index (dims={self.dims}) ready")

    def search_similar_posts(self, query_embedding: np.ndarray, limit: int = 5):
        with self.graph.driver.session() as session:
            result = session.run("""
                CALL db.index.vector.queryNodes('post_embeddings', $limit, $embedding)
                YIELD node, score
                RETURN node.id AS post_id,
                       node.subject AS subject,
                       node.content AS content,
                       score
            """, 
                limit=limit,
                embedding=query_embedding.tolist()
            )
            return [dict(r) for r in result]
        
    # VECTOR SEARCH + CONSTRAINTS (GRAPHRAG)
    def search_similar_posts_filtered(
        self,
        query_embedding: np.ndarray,
        limit: int = 5,
        course_id: str | None = None,
        semester: str | None = None,
        author: str | None = None,
        only_roots: bool = False,
        only_replies: bool = False,
        before: str | None = None,   # ISO 8601, e.g. "2025-01-01T00:00:00Z" or "2025-01-01"
        after: str | None = None
    ):
        filters = []
        if course_id:   filters.append("node.course_id = $course_id")
        if semester:    filters.append("node.course_semester = $semester")
        if author:      filters.append("node.author_name = $author")
        if only_roots:  filters.append("node.is_thread_root = true")
        if only_replies:filters.append("node.is_reply = true")
        if before:      filters.append("datetime(node.post_datetime) < datetime($before)")
        if after:       filters.append("datetime(node.post_datetime) >= datetime($after)")

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        cypher = f"""
        CALL db.index.vector.queryNodes('post_embeddings', $limit * 5, $embedding)
        YIELD node, score
        {where_clause}
        RETURN node.id AS post_id,
            node.subject AS subject,
            node.content AS content,
            node.course_id AS course_id,
            node.post_datetime AS post_datetime,
            score
        ORDER BY score DESC
        LIMIT $limit
        """
        with self.graph.driver.session() as s:
            res = s.run(
                cypher,
                limit=limit,
                embedding=query_embedding.tolist(),
                course_id=course_id,
                semester=semester,
                author=author,
                before=before,
                after=after
            )
            return [dict(r) for r in res]
