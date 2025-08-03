from .a_load_forum_data import load_forum_data
from .b_embedder_builder import TextEmbedder
from .d_neo import GraphStore
from .b_vector_search import VectorSearch

posts = load_forum_data("./B_data/course_40280/forums/40280_forum_02_studierendenforum__2025-08-03T00-26+00-00.json")

embedder = TextEmbedder("distiluse-base-multilingual-cased-v2")
embs = embedder.embed_batch([p.get_text_for_embedding() for p in posts])

db = GraphStore(password="password")
for p, e in zip(posts, embs):
    db.store_post(p, e)
db.link_replies(posts)

vs = VectorSearch(db, dims=512)
query = "Portfolio Punkte Bewertung"
query_embedding = embedder.embed_text(query)
results = vs.search_similar_posts(query_embedding, limit=3)

for r in results:
    print(r)

db.close()
