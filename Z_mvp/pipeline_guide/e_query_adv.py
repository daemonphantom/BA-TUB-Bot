import argparse
from .b_embedder import TextEmbedder
from .c_neo import GraphStore
from .d_vector_search import VectorSearch

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--limit", type=int, default=5)
    # Add GraphRAG filtering options
    ap.add_argument("--course-id")
    ap.add_argument("--semester") 
    ap.add_argument("--author")
    ap.add_argument("--only-roots", action="store_true")
    ap.add_argument("--only-replies", action="store_true")
    args = ap.parse_args()

    db = GraphStore(password="password")
    embedder = TextEmbedder("distiluse-base-multilingual-cased-v2")
    vs = VectorSearch(db, dims=512)

    q_emb = embedder.embed_text(args.query)
    
    # Use the GraphRAG filtered search
    results = vs.search_similar_posts_filtered(
        q_emb, 
        limit=args.limit,
        course_id=args.course_id,
        semester=args.semester,
        author=args.author,
        only_roots=args.only_roots,
        only_replies=args.only_replies
    )

    print(f"🔍 {args.query}")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['score']:.3f} | {r['subject']} | Course: {r['course_id']}")
        print(f"   {r['content'][:120]}...\n")

    db.close()

if __name__ == "__main__":
    main()