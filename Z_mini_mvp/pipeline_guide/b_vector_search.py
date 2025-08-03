from .d_neo import GraphStore
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
