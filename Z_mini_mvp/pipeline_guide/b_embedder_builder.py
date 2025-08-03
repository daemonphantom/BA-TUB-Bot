from sentence_transformers import SentenceTransformer
import numpy as np


class TextEmbedder:
    """Converts text to vector embeddings"""
    #"distiluse-base-multilingual-cased-v2"
    #"jinaai/jina-embeddings-v2-base-de"
    def __init__(self, model_name: str = "distiluse-base-multilingual-cased-v2"):
        print(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        
    def embed_text(self, text: str) -> np.ndarray:
        """Convert single text to embedding"""
        return self.model.encode([text])[0]
    
    def embed_batch(self, texts: list[str]) -> np.ndarray:
        """Convert multiple texts to embeddings (more efficient)"""
        return self.model.encode(texts)

""" 
# Test the embedder
embedder = TextEmbedder()

# Test with your forum post
test_text = "Bei der Portfoliopunkte Bewertung steht unten Kurs gesamt"
embedding = embedder.embed_text(test_text)
print(f"Text: {test_text}")
print(f"Embedding shape: {embedding.shape}")
print(f"First 5 values: {embedding[:5]}")
"""