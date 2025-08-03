import argparse
from .b_embedder_builder import TextEmbedder
from .d_neo import GraphStore
from .b_vector_search import VectorSearch

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()

    db = GraphStore(password="password")
    embedder = TextEmbedder("distiluse-base-multilingual-cased-v2")
    vs = VectorSearch(db, dims=512)  # distiluse = 512

    q_emb = embedder.embed_text(args.query)
    results = vs.search_similar_posts(q_emb, limit=args.limit)

    print(f"🔍 {args.query}")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['score']:.3f} | {r['subject']}")
        print(f"   {r['content'][:120]}...\n")

    db.close()

if __name__ == "__main__":
    main()
