from .a_load_forum_data import load_forum_data
from .b_embedder_builder import TextEmbedder
from sklearn.metrics.pairwise import cosine_similarity


embedder = TextEmbedder()

text1 = "Portfolio Punkte Bewertung"
text2 = "Portfoliopunkte berechnen"
text3 = "Wetter heute schön"

emb1 = embedder.embed_text(text1)
emb2 = embedder.embed_text(text2)
emb3 = embedder.embed_text(text3)

sim_1_2 = cosine_similarity([emb1], [emb2])[0][0]
sim_1_3 = cosine_similarity([emb1], [emb3])[0][0]

print(f"Similarity Portfolio texts: {sim_1_2:.3f}")
print(f"Similarity Portfolio vs Weather: {sim_1_3:.3f}")


""" # 1. Load forum data
posts = load_forum_data('./B_data/course_40280/forums/40280_forum_02_studierendenforum__2025-08-03T00-26+00-00.json')
print(f"Loaded {len(posts)} posts")

# 2. Print info about posts 2–4 (which you suspect are in same thread)
for i in range(2, 5):
    p = posts[i]
    print(f"[{i}] Thread ID: {p.thread_id} | Post ID: {p.post_id} | Subject: {p.subject}")
    print(f"Content: {p.content[:80]}...\n")

# 3. Embed and compare
embedder = TextEmbedder("distiluse-base-multilingual-cased-v2")
texts = [posts[i].content for i in range(2, 5)]
embeddings = embedder.embed_batch(texts)

sim_matrix = cosine_similarity(embeddings)
print("\nSimilarity Matrix:")
for row in sim_matrix:
    print("  ".join(f"{sim:.3f}" for sim in row))
"""

"""
# Compare similarity
for i in range(len(embeddings)):
    for j in range(i + 1, len(embeddings)):
        sim = cosine_similarity([embeddings[i]], [embeddings[j]])[0][0]
        print(f"Similarity post {i+1} vs post {j+1}: {sim:.3f}")


embedder = TextEmbedder()

# Test with your forum post
test_text = "Bei der Portfoliopunkte Bewertung steht unten Kurs gesamt"
embedding = embedder.embed_text(test_text)
print(f"Text: {test_text}")
print(f"Embedding shape: {embedding.shape}")
print(f"First 5 values: {embedding[:5]}")
 """