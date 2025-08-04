from sentence_transformers import SentenceTransformer
import numpy as np

class TextEmbedder:
    def __init__(self, model_name: str = "distiluse-base-multilingual-cased-v2"): # MODELS: "distiluse-base-multilingual-cased-v2" "jinaai/jina-embeddings-v2-base-de"
        print(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        
    # Convert single text to embedding
    def embed_text(self, text: str) -> np.ndarray:
        return self.model.encode([text])[0]
    
    # Convert multiple texts to embeddings (efficient)
    def embed_list(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts)