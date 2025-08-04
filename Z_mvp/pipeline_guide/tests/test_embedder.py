from ..a_load_forum_data import load_forum_data
from ..b_embedder import TextEmbedder
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

