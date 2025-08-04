#!/usr/bin/env python3
"""
CLI Interface for Forum GraphRAG System
Usage: python cli.py [command] [options]
"""

import argparse
import json
import sys
import os
from pathlib import Path
from typing import Dict, Any
import logging

# Assuming the main GraphRAG system is in graphrag.py
try:
    from forum_graphrag import ForumGraphRAG
except ImportError:
    print("❌ Error: Could not import ForumGraphRAG. Make sure graphrag.py is in the same directory.")
    sys.exit(1)

def setup_logging(level: str = "INFO"):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def load_config() -> Dict[str, str]:
    """Load configuration from environment variables or .env file"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    return {
        'neo4j_uri': os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
        'neo4j_user': os.getenv('NEO4J_USER', 'neo4j'),
        'neo4j_password': os.getenv('NEO4J_PASSWORD', 'password'),
        'embedding_model': os.getenv('EMBEDDING_MODEL', 'jinaai/jina-embeddings-v2-base-de'),
        'forum_data_path': os.getenv('FORUM_DATA_PATH', 'forum_data.json'),
        'log_level': os.getenv('LOG_LEVEL', 'INFO')
    }

def build_command(args):
    """Build the knowledge graph from forum data"""
    config = load_config()
    setup_logging(config['log_level'])
    
    if not Path(args.input_file).exists():
        print(f"❌ Error: Input file '{args.input_file}' not found.")
        return
    
    print("🚀 Initializing Forum GraphRAG System...")
    try:
        graphrag = ForumGraphRAG(
            neo4j_uri=config['neo4j_uri'],
            neo4j_user=config['neo4j_user'],
            neo4j_password=config['neo4j_password']
        )
        
        print(f"📚 Building knowledge graph from {args.input_file}...")
        graphrag.build_from_json(args.input_file)
        
        print("✅ Knowledge graph built successfully!")
        
        if args.stats:
            print_statistics(graphrag)
        
    except Exception as e:
        print(f"❌ Error building knowledge graph: {e}")
    finally:
        graphrag.close()

def query_command(args):
    """Query the knowledge graph"""
    config = load_config()
    setup_logging(config['log_level'])
    
    print("🔍 Connecting to GraphRAG system...")
    try:
        graphrag = ForumGraphRAG(
            neo4j_uri=config['neo4j_uri'],
            neo4j_user=config['neo4j_user'],
            neo4j_password=config['neo4j_password']
        )
        
        print(f"Query: {args.query}")
        print("-" * 50)
        
        results = graphrag.query(
            args.query, 
            k_vector=args.k_vector, 
            k_graph=args.k_graph
        )
        
        print_query_results(results, args.output_format)
        
        if args.output_file:
            save_results_to_file(results, args.output_file)
            print(f"💾 Results saved to {args.output_file}")
        
    except Exception as e:
        print(f"❌ Error querying system: {e}")
    finally:
        graphrag.close()

def interactive_command(args):
    """Start interactive query session"""
    config = load_config()
    setup_logging(config['log_level'])
    
    print("🚀 Starting interactive GraphRAG session...")
    print("Type 'exit' or 'quit' to end the session.")
    print("Type 'help' for available commands.")
    
    try:
        graphrag = ForumGraphRAG(
            neo4j_uri=config['neo4j_uri'],
            neo4j_user=config['neo4j_user'],
            neo4j_password=config['neo4j_password']
        )
        
        while True:
            try:
                query = input("\n🔍 Enter your query: ").strip()
                
                if query.lower() in ['exit', 'quit']:
                    break
                elif query.lower() == 'help':
                    print_interactive_help()
                    continue
                elif query.lower() == 'stats':
                    print_statistics(graphrag)
                    continue
                elif not query:
                    continue
                
                print("-" * 50)
                results = graphrag.query(query, k_vector=5, k_graph=10)
                print_query_results(results, 'compact')
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        print("\n👋 Goodbye!")
        
    except Exception as e:
        print(f"❌ Error starting interactive session: {e}")
    finally:
        graphrag.close()

def print_query_results(results: Dict[str, Any], format_type: str = 'detailed'):
    """Print query results in specified format"""
    
    if format_type == 'json':
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return
    
    print(f"📊 Found {len(results['vector_results'])} relevant posts:")
    
    for i, result in enumerate(results['vector_results'], 1):
        if format_type == 'compact':
            print(f"\n{i}. 📝 {result['subject']} (Score: {result['score']:.3f})")
            print(f"   💬 {result['content'][:100]}...")
        else:
            print(f"\n{'='*60}")
            print(f"Result {i} - Score: {result['score']:.3f}")
            print(f"Subject: {result['subject']}")
            print(f"Post ID: {result['post_id']}")
            print(f"Content: {result['content']}")
            
            # Show graph context if available
            graph_result = next(
                (gr for gr in results['graph_results'] if gr['vector_result']['post_id'] == result['post_id']), 
                None
            )
            if graph_result and graph_result['context']:
                context = graph_result['context']
                if context.get('related_posts'):
                    print(f"Related posts: {len(context['related_posts'])}")
                if context.get('thread_posts'):
                    print(f"Thread posts: {len(context['thread_posts'])}")

def print_statistics(graphrag):
    """Print database statistics"""
    print("\n📈 Database Statistics:")
    try:
        with graphrag.graph_store.driver.session() as session:
            # Count nodes
            result = session.run("MATCH (n) RETURN labels(n) as label, count(n) as count")
            print("\nNode counts:")
            for record in result:
                print(f"  {record['label'][0] if record['label'] else 'Unknown'}: {record['count']}")
            
            # Count relationships
            result = session.run("MATCH ()-[r]->() RETURN type(r) as rel_type, count(r) as count")
            print("\nRelationship counts:")
            for record in result:
                print(f"  {record['rel_type']}: {record['count']}")
                
    except Exception as e:
        print(f"❌ Error getting statistics: {e}")

def print_interactive_help():
    """Print help for interactive mode"""
    print("""
🔧 Interactive Commands:
  - Enter any question to search the knowledge graph
  - 'stats' - Show database statistics
  - 'help' - Show this help message
  - 'exit' or 'quit' - End the session
    
💡 Example queries:
  - "Portfolio Punkte Bewertung"
  - "Wie funktioniert die Bewertung?"
  - "Wer hat geantwortet?"
  - "Einführung Programmierung"
    """)

def save_results_to_file(results: Dict[str, Any], filename: str):
    """Save query results to a file"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

def status_command(args):
    """Check system status"""
    config = load_config()
    setup_logging(config['log_level'])
    
    print("🔍 Checking Forum GraphRAG System Status...")
    
    # Check Neo4j connection
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            config['neo4j_uri'],
            auth=(config['neo4j_user'], config['neo4j_password'])
        )
        with driver.session() as session:
            session.run("RETURN 1")
        print("✅ Neo4j connection: OK")
        driver.close()
    except Exception as e:
        print(f"❌ Neo4j connection: FAILED ({e})")
        return
    
    # Check if data exists
    try:
        graphrag = ForumGraphRAG(
            neo4j_uri=config['neo4j_uri'],
            neo4j_user=config['neo4j_user'],
            neo4j_password=config['neo4j_password']
        )
        print_statistics(graphrag)
        graphrag.close()
    except Exception as e:
        print(f"❌ Error checking data: {e}")

def export_command(args):
    """Export knowledge graph data"""
    config = load_config()
    setup_logging(config['log_level'])
    
    print(f"📤 Exporting knowledge graph to {args.output_file}...")
    
    try:
        graphrag = ForumGraphRAG(
            neo4j_uri=config['neo4j_uri'],
            neo4j_user=config['neo4j_user'],
            neo4j_password=config['neo4j_password']
        )
        
        export_data = {}
        
        with graphrag.graph_store.driver.session() as session:
            # Export posts
            if args.include_posts:
                result = session.run("""
                    MATCH (p:Post)
                    RETURN p.post_id as post_id, p.subject as subject, 
                           p.content as content, p.author as author,
                           p.post_datetime as datetime
                """)
                export_data['posts'] = [dict(record) for record in result]
            
            # Export knowledge triples
            if args.include_triples:
                result = session.run("""
                    MATCH (s:Entity)-[r:RELATION]->(o:Entity)
                    RETURN s.name as subject, r.type as predicate, 
                           o.name as object, r.confidence as confidence,
                           r.source_post_id as source_post_id
                """)
                export_data['triples'] = [dict(record) for record in result]
            
            # Export graph statistics
            export_data['statistics'] = {
                'export_timestamp': results['retrieval_timestamp'] if 'results' in locals() else None,
                'total_posts': len(export_data.get('posts', [])),
                'total_triples': len(export_data.get('triples', []))
            }
        
        # Save to file
        with open(args.output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Export completed: {args.output_file}")
        print(f"   Posts: {len(export_data.get('posts', []))}")
        print(f"   Triples: {len(export_data.get('triples', []))}")
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
    finally:
        graphrag.close()

def clear_command(args):
    """Clear all data from the knowledge graph"""
    config = load_config()
    setup_logging(config['log_level'])
    
    if not args.confirm:
        response = input("⚠️  This will delete ALL data from the knowledge graph. Continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Operation cancelled.")
            return
    
    print("🗑️  Clearing knowledge graph...")
    
    try:
        graphrag = ForumGraphRAG(
            neo4j_uri=config['neo4j_uri'],
            neo4j_user=config['neo4j_user'],
            neo4j_password=config['neo4j_password']
        )
        
        with graphrag.graph_store.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        
        print("✅ Knowledge graph cleared successfully!")
        
    except Exception as e:
        print(f"❌ Error clearing database: {e}")
    finally:
        graphrag.close()

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Forum GraphRAG System CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py build forum_data.json
  python cli.py query "Portfolio Punkte"
  python cli.py query "Bewertung" --k-vector 10 --output-file results.json
  python cli.py interactive
  python cli.py status
  python cli.py export output.json --include-posts --include-triples
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Build command
    build_parser = subparsers.add_parser('build', help='Build knowledge graph from forum data')
    build_parser.add_argument('input_file', help='Path to forum JSON file')
    build_parser.add_argument('--stats', action='store_true', help='Show statistics after building')
    build_parser.set_defaults(func=build_command)
    
    # Query command
    query_parser = subparsers.add_parser('query', help='Query the knowledge graph')
    query_parser.add_argument('query', help='Query string')
    query_parser.add_argument('--k-vector', type=int, default=5, help='Number of vector results (default: 5)')
    query_parser.add_argument('--k-graph', type=int, default=10, help='Number of graph results (default: 10)')
    query_parser.add_argument('--output-format', choices=['detailed', 'compact', 'json'], 
                             default='detailed', help='Output format (default: detailed)')
    query_parser.add_argument('--output-file', help='Save results to file')
    query_parser.set_defaults(func=query_command)
    
    # Interactive command
    interactive_parser = subparsers.add_parser('interactive', help='Start interactive query session')
    interactive_parser.set_defaults(func=interactive_command)
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Check system status')
    status_parser.set_defaults(func=status_command)
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export knowledge graph data')
    export_parser.add_argument('output_file', help='Output file path')
    export_parser.add_argument('--include-posts', action='store_true', help='Include posts in export')
    export_parser.add_argument('--include-triples', action='store_true', help='Include knowledge triples in export')
    export_parser.set_defaults(func=export_command)
    
    # Clear command
    clear_parser = subparsers.add_parser('clear', help='Clear all data from knowledge graph')
    clear_parser.add_argument('--confirm', action='store_true', help='Skip confirmation prompt')
    clear_parser.set_defaults(func=clear_command)
    
    # Parse arguments and execute command
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    try:
        args.func(args)
    except KeyboardInterrupt:
        print("\n👋 Operation cancelled by user.")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()