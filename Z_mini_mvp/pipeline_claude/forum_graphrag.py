import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import asyncio
from dataclasses import dataclass
from pathlib import Path

# Core dependencies
import numpy as np
from sentence_transformers import SentenceTransformer
from neo4j import GraphDatabase
import networkx as nx
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
import spacy

# Optional: For better text processing
try:
    import tiktoken
except ImportError:
    tiktoken = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ForumPost:
    """Structured representation of a forum post"""
    post_id: str
    thread_id: str
    subject: str
    content: str
    author: str
    post_datetime: str
    course_id: str
    course_name: str
    semester: str
    faculty: str
    is_reply: bool
    response_to: Optional[str]
    permalink: str
    attachments: List[str]
    links: List[Dict[str, str]]
    embedding: Optional[np.ndarray] = None

@dataclass
class KnowledgeTriple:
    """Knowledge graph triple (subject, predicate, object)"""
    subject: str
    predicate: str
    object: str
    confidence: float = 1.0
    source_post_id: str = ""

class EmbeddingManager:
    """Handles text embedding using Jina embeddings"""
    
    def __init__(self, model_name: str = "jinaai/jina-embeddings-v2-base-de"):
        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Embedding dimension: {self.dimension}")
    
    def embed_texts(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """Embed a list of texts"""
        logger.info(f"Embedding {len(texts)} texts...")
        embeddings = self.model.encode(
            texts, 
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        return embeddings
    
    def embed_single(self, text: str) -> np.ndarray:
        """Embed a single text"""
        return self.model.encode([text])[0]

class Neo4jGraphStore:
    """Neo4j graph database manager"""
    
    def __init__(self, uri: str = "bolt://localhost:7687", user: str = "neo4j", password: str = "password"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self._create_constraints()
    
    def _create_constraints(self):
        """Create database constraints and indexes"""
        with self.driver.session() as session:
            # Create constraints
            constraints = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Post) REQUIRE p.post_id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Thread) REQUIRE t.thread_id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (a:Author) REQUIRE a.name IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Course) REQUIRE c.course_id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE",
            ]
            
            for constraint in constraints:
                try:
                    session.run(constraint)
                except Exception as e:
                    logger.warning(f"Constraint creation warning: {e}")
            
            # Create vector index for embeddings
            try:
                session.run("""
                    CREATE VECTOR INDEX post_embeddings IF NOT EXISTS
                    FOR (p:Post) ON (p.embedding)
                    OPTIONS {indexConfig: {
                        `vector.dimensions`: $dimension,
                        `vector.similarity_function`: 'cosine'
                    }}
                """, dimension=768)  # Jina embeddings dimension
            except Exception as e:
                logger.warning(f"Vector index creation warning: {e}")
    
    def store_post(self, post: ForumPost):
        """Store a forum post with its relationships"""
        with self.driver.session() as session:
            # Create post node
            session.run("""
                MERGE (p:Post {post_id: $post_id})
                SET p.thread_id = $thread_id,
                    p.subject = $subject,
                    p.content = $content,
                    p.post_datetime = $post_datetime,
                    p.is_reply = $is_reply,
                    p.response_to = $response_to,
                    p.permalink = $permalink,
                    p.embedding = $embedding
                
                MERGE (t:Thread {thread_id: $thread_id})
                MERGE (a:Author {name: $author})
                MERGE (c:Course {course_id: $course_id})
                SET c.name = $course_name,
                    c.semester = $semester,
                    c.faculty = $faculty
                
                MERGE (p)-[:POSTED_IN]->(t)
                MERGE (p)-[:AUTHORED_BY]->(a)
                MERGE (p)-[:BELONGS_TO]->(c)
            """, 
                post_id=post.post_id,
                thread_id=post.thread_id,
                subject=post.subject,
                content=post.content,
                post_datetime=post.post_datetime,
                is_reply=post.is_reply,
                response_to=post.response_to,
                permalink=post.permalink,
                embedding=post.embedding.tolist() if post.embedding is not None else None,
                author=post.author,
                course_id=post.course_id,
                course_name=post.course_name,
                semester=post.semester,
                faculty=post.faculty
            )
            
            # Create reply relationship if applicable
            if post.is_reply and post.response_to:
                session.run("""
                    MATCH (reply:Post {post_id: $reply_id})
                    MATCH (original:Post {post_id: $original_id})
                    MERGE (reply)-[:REPLIES_TO]->(original)
                """, reply_id=post.post_id, original_id=post.response_to)
    
    def store_knowledge_triple(self, triple: KnowledgeTriple):
        """Store a knowledge triple in the graph"""
        with self.driver.session() as session:
            session.run("""
                MERGE (s:Entity {name: $subject})
                MERGE (o:Entity {name: $object})
                MERGE (s)-[r:RELATION {
                    type: $predicate,
                    confidence: $confidence,
                    source_post_id: $source_post_id
                }]->(o)
            """, 
                subject=triple.subject,
                predicate=triple.predicate,
                object=triple.object,
                confidence=triple.confidence,
                source_post_id=triple.source_post_id
            )
    
    def vector_search(self, query_embedding: np.ndarray, limit: int = 10) -> List[Dict]:
        """Perform vector similarity search"""
        with self.driver.session() as session:
            result = session.run("""
                CALL db.index.vector.queryNodes('post_embeddings', $limit, $query_embedding)
                YIELD node, score
                RETURN node.post_id as post_id, 
                       node.content as content,
                       node.subject as subject,
                       score
                ORDER BY score DESC
            """, query_embedding=query_embedding.tolist(), limit=limit)
            
            return [dict(record) for record in result]
    
    def get_post_context(self, post_id: str, depth: int = 2) -> Dict:
        """Get contextual information around a post"""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (p:Post {post_id: $post_id})
                OPTIONAL MATCH (p)-[:REPLIES_TO*1..$depth]-(related:Post)
                OPTIONAL MATCH (p)-[:POSTED_IN]->(t:Thread)<-[:POSTED_IN]-(thread_posts:Post)
                RETURN p, collect(DISTINCT related) as related_posts, 
                       collect(DISTINCT thread_posts) as thread_posts
            """, post_id=post_id, depth=depth)
            
            record = result.single()
            if record:
                return {
                    'main_post': dict(record['p']),
                    'related_posts': [dict(post) for post in record['related_posts']],
                    'thread_posts': [dict(post) for post in record['thread_posts']]
                }
            return {}
    
    def close(self):
        """Close database connection"""
        self.driver.close()

class KnowledgeExtractor:
    """Extract knowledge triples from forum posts"""
    
    def __init__(self, language: str = "de"):
        try:
            self.nlp = spacy.load(f"{language}_core_news_sm")
        except OSError:
            logger.warning(f"German spaCy model not found. Install with: python -m spacy download de_core_news_sm")
            self.nlp = None
    
    def extract_entities(self, text: str) -> List[str]:
        """Extract named entities from text"""
        if not self.nlp:
            return []
        
        doc = self.nlp(text)
        entities = [ent.text.strip() for ent in doc.ents if len(ent.text.strip()) > 2]
        return list(set(entities))
    
    def extract_triples(self, post: ForumPost) -> List[KnowledgeTriple]:
        """Extract knowledge triples from a forum post"""
        triples = []
        
        # Extract basic relationships
        entities = self.extract_entities(post.content)
        
        # Author-Post relationship
        triples.append(KnowledgeTriple(
            subject=post.author,
            predicate="AUTHORED",
            object=f"Post_{post.post_id}",
            source_post_id=post.post_id
        ))
        
        # Course-Post relationship
        triples.append(KnowledgeTriple(
            subject=post.course_name,
            predicate="CONTAINS_POST",
            object=f"Post_{post.post_id}",
            source_post_id=post.post_id
        ))
        
        # Entity-Post relationships
        for entity in entities:
            triples.append(KnowledgeTriple(
                subject=entity,
                predicate="MENTIONED_IN",
                object=f"Post_{post.post_id}",
                source_post_id=post.post_id
            ))
        
        # Subject-based relationships
        if "Portfolio" in post.subject or "Portfolio" in post.content:
            triples.append(KnowledgeTriple(
                subject="Portfolio",
                predicate="DISCUSSED_IN",
                object=f"Post_{post.post_id}",
                source_post_id=post.post_id
            ))
        
        return triples

class GraphRAGRetriever:
    """GraphRAG retrieval system"""
    
    def __init__(self, embedding_manager: EmbeddingManager, graph_store: Neo4jGraphStore):
        self.embedding_manager = embedding_manager
        self.graph_store = graph_store
    
    def retrieve(self, query: str, k_vector: int = 5, k_graph: int = 10) -> Dict[str, Any]:
        """Retrieve relevant information using both vector and graph methods"""
        
        # Vector-based retrieval
        query_embedding = self.embedding_manager.embed_single(query)
        vector_results = self.graph_store.vector_search(query_embedding, limit=k_vector)
        
        # Graph-based retrieval - expand context for each vector result
        graph_results = []
        for result in vector_results:
            context = self.graph_store.get_post_context(result['post_id'])
            graph_results.append({
                'vector_result': result,
                'context': context
            })
        
        return {
            'query': query,
            'vector_results': vector_results,
            'graph_results': graph_results,
            'retrieval_timestamp': datetime.now().isoformat()
        }

class ForumGraphRAG:
    """Main GraphRAG system for forum data"""
    
    def __init__(self, neo4j_uri: str = "bolt://localhost:7687", 
                 neo4j_user: str = "neo4j", neo4j_password: str = "password"):
        self.embedding_manager = EmbeddingManager()
        self.graph_store = Neo4jGraphStore(neo4j_uri, neo4j_user, neo4j_password)
        self.knowledge_extractor = KnowledgeExtractor()
        self.retriever = GraphRAGRetriever(self.embedding_manager, self.graph_store)
    
    def load_forum_data(self, json_file_path: str):
        """Load and process forum data from JSON file"""
        logger.info(f"Loading forum data from {json_file_path}")
        
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        posts = []
        for post_data in data.get('posts', []):
            post = ForumPost(
                post_id=post_data['metadata']['post_id'],
                thread_id=post_data['metadata']['thread_id'],
                subject=post_data['metadata']['subject'],
                content=post_data['content'],
                author=post_data['metadata']['author'],
                post_datetime=post_data['metadata']['post_datetime'],
                course_id=post_data['metadata']['course']['id'],
                course_name=post_data['metadata']['course']['name'],
                semester=post_data['metadata']['course']['semester'],
                faculty=post_data['metadata']['course']['faculty'],
                is_reply=post_data['metadata']['is_reply'],
                response_to=post_data['metadata']['response_to'],
                permalink=post_data['metadata']['permalink'],
                attachments=post_data['metadata']['attachments'],
                links=post_data['metadata']['links']
            )
            posts.append(post)
        
        return posts
    
    def process_posts(self, posts: List[ForumPost], batch_size: int = 32):
        """Process posts: embed content, extract knowledge, store in graph"""
        logger.info(f"Processing {len(posts)} posts...")
        
        # Embed all post contents
        contents = [post.content for post in posts]
        embeddings = self.embedding_manager.embed_texts(contents, batch_size)
        
        # Assign embeddings to posts
        for post, embedding in zip(posts, embeddings):
            post.embedding = embedding
        
        # Store posts in graph database
        for post in posts:
            logger.info(f"Storing post {post.post_id}")
            self.graph_store.store_post(post)
            
            # Extract and store knowledge triples
            triples = self.knowledge_extractor.extract_triples(post)
            for triple in triples:
                self.graph_store.store_knowledge_triple(triple)
    
    def build_from_json(self, json_file_path: str):
        """Complete pipeline: load, embed, and store forum data"""
        posts = self.load_forum_data(json_file_path)
        self.process_posts(posts)
        logger.info("GraphRAG system build complete!")
    
    def query(self, question: str, k_vector: int = 5, k_graph: int = 10) -> Dict[str, Any]:
        """Query the GraphRAG system"""
        return self.retriever.retrieve(question, k_vector, k_graph)
    
    def close(self):
        """Clean up resources"""
        self.graph_store.close()

# Example usage and CLI interface
def main():
    """Main function demonstrating usage"""
    
    # Initialize GraphRAG system
    print("🚀 Initializing Forum GraphRAG System...")
    graphrag = ForumGraphRAG()
    
    try:
        # Build knowledge graph from your JSON file
        print("📚 Building knowledge graph from forum data...")
        graphrag.build_from_json("forum_data.json")  # Replace with your JSON file path
        
        print("✅ Knowledge graph built successfully!")
        
        # Example queries
        example_queries = [
            "Portfolio Punkte Bewertung",
            "Wie werden die Portfoliopunkte berechnet?",
            "Wer ist Uwe Kuehn?",
            "Einführung in die Programmierung",
            "ISIS Aktivitäten"
        ]
        
        print("\n🔍 Testing example queries...")
        for query in example_queries:
            print(f"\nQuery: {query}")
            results = graphrag.query(query, k_vector=3, k_graph=5)
            
            print("Vector Results:")
            for i, result in enumerate(results['vector_results'], 1):
                print(f"  {i}. Score: {result['score']:.3f}")
                print(f"     Subject: {result['subject']}")
                print(f"     Content: {result['content'][:100]}...")
            
            print(f"Graph Context: {len(results['graph_results'])} expanded results")
            print("-" * 50)
    
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        graphrag.close()

if __name__ == "__main__":
    main()