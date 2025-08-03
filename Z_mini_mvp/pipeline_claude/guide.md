# Forum GraphRAG System

A complete GraphRAG (Graph Retrieval-Augmented Generation) system for analyzing forum data using open-source tools.

## 🎯 Features

- **Vector Embeddings**: Uses Jina embeddings for German text
- **Knowledge Graph**: Neo4j for storing posts and relationships
- **GraphRAG Retrieval**: Combines vector search with graph traversal
- **Open Source**: All components are free and open-source
- **CLI Interface**: Easy-to-use command line tools
- **Jupyter Integration**: Interactive notebooks for exploration

## 🛠️ Tech Stack

- **Embeddings**: `jinaai/jina-embeddings-v2-base-de` (German language support)
- **Graph Database**: Neo4j Community Edition
- **Vector Search**: sentence-transformers
- **Knowledge Extraction**: spaCy (German NLP model)
- **Additional**: NetworkX, scikit-learn, pandas

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.8+
- Neo4j Database (Community Edition)
- 8GB+ RAM recommended

### 2. Installation

```bash
# Clone or download the system files
git clone <your-repo> forum-graphrag
cd forum-graphrag

# Install Python dependencies
pip install -r requirements.txt

# Install German language model for spaCy
python -m spacy download de_core_news_sm

# Set up Neo4j (Option A: Docker)
docker-compose up -d

# Or (Option B: Local installation)
# Download and install Neo4j Community Edition from neo4j.com
```

### 3. Configuration

```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your settings
# NEO4J_URI=bolt://localhost:7687
# NEO4J_USER=neo4j
# NEO4J_PASSWORD=password
```

### 4. Build Knowledge Graph

```bash
# Build from your forum JSON file
python cli.py build forum_data.json --stats

# Check system status
python cli.py status
```

### 5. Query the System

```bash
# Simple query
python cli.py query "Portfolio Punkte Bewertung"

# Advanced query with options
python cli.py query "Wie funktioniert die Bewertung?" --k-vector 10 --output-file results.json

# Interactive mode
python cli.py interactive
```

## 📊 Your Task Status

Based on your requirements, here's the progress:

### ✅ Completed Tasks

1. **Chunked forum posts** ✅ - JSON parsing implemented
2. **Embed chunks** ✅ - Jina embeddings integration
3. **Store in Neo4j** ✅ - Complete graph storage system
4. **Build KG relations** ✅ - Knowledge extraction and relationship building
5. **Vector index** ✅ - Neo4j vector indexing for similarity search
6. **GraphRAG retriever** ✅ - Hybrid vector + graph retrieval
7. **LLM integration** 🔄 - Framework ready for LLaMA 3.3 70B

### 🔄 Next Steps

The system is ready for LLaMA 3.3 70B integration. You can add any open-source LLM:

```python
# Example LLM integration
class LLMGenerator:
    def __init__(self, model_path="path/to/llama-3.3-70b"):
        # Load your LLM here
        pass
    
    def generate_response(self, query, context):
        # Generate response using retrieved context
        pass

# Add to GraphRAG system
graphrag.add_llm_generator(LLMGenerator())
```

## 📁 File Structure

```
forum-graphrag/
├── forum_graphrag.py          # Main GraphRAG system
├── cli.py                     # Command line interface
├── notebook.ipynb             # Jupyter notebook for exploration
├── requirements.txt           # Python dependencies
├── docker-compose.yml         # Neo4j setup
├── setup.sh                   # Setup script
├── .env.example               # Environment template
└── README.md                  # This file
```

## 🔧 Usage Examples

### CLI Usage

```bash
# Build knowledge graph
python cli.py build forum_data.json

# Query examples
python cli.py query "Portfolio Punkte"
python cli.py query "ISIS Aktivitäten" --k-vector 5
python cli.py query "Einführung Programmierung" --output-format json

# Interactive session
python cli.py interactive

# Export data
python cli.py export output.json --include-posts --include-triples

# System management
python cli.py status
python cli.py clear --confirm
```

### Python API Usage

```python
from forum_graphrag import ForumGraphRAG

# Initialize system
graphrag = ForumGraphRAG()

# Build knowledge graph
graphrag.build_from_json("forum_data.json")

# Query the system
results = graphrag.query("Portfolio Punkte Bewertung")

# Process results
for result in results['vector_results']:
    print(f"Score: {result['score']}")
    print(f"Content: {result['content']}")

# Clean up
graphrag.close()
```

### Jupyter Notebook

1. Open `notebook.ipynb`
2. Update the `FORUM_DATA_FILE` path
3. Run all cells to build and explore your knowledge graph
4. Use the interactive query function for testing

## 🎛️ Configuration Options

### Neo4j Settings

```bash
# .env file
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

### Embedding Model

```bash
# Use different embedding model
EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-de
```

### Performance Tuning

```python
# Adjust batch sizes and limits
graphrag.process_posts(posts, batch_size=16)  # Smaller batch for less memory
results = graphrag.query(query, k_vector=10, k_graph=20)  # More results
```

## 🐛 Troubleshooting

### Neo4j Connection Issues

```bash
# Check if Neo4j is running
python cli.py status

# Reset database
python cli.py clear --confirm

# Check Docker logs
docker-compose logs neo4j
```

### Memory Issues

```python
# Reduce batch size
graphrag.process_posts(posts, batch_size=8)

# Or process in chunks
for i in range(0, len(posts), 50):
    chunk = posts[i:i+50]
    graphrag.process_posts(chunk)
```

### German Language Model

```bash
# Install German spaCy model
python -m spacy download de_core_news_sm

# Verify installation
python -c "import spacy; nlp = spacy.load('de_core_news_sm'); print('OK')"
```

## 📈 Performance Optimization

### Database Indexing

The system automatically creates:
- Vector indexes for similarity search
- Node constraints for uniqueness
- Relationship indexes for fast traversal

### Memory Management

- Processes embeddings in batches
- Uses efficient Neo4j queries
- Minimizes memory footprint

### Query Optimization

- Combines vector and graph search
- Limits result sets appropriately
- Caches embeddings in database

## 🔮 Future Enhancements

1. **LLM Integration**: Add LLaMA 3.3 70B for response generation
2. **Web Interface**: Build a React/Flask web UI
3. **Real-time Updates**: Stream processing for new forum posts
4. **Advanced Analytics**: Sentiment analysis, topic modeling
5. **Multi-language**: Extend to other languages

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📝 License

This project is open-source and uses only free/open-source components:

- Neo4j Community Edition (GPL)
- Sentence Transformers (Apache 2.0)
- spaCy (MIT)
- All other dependencies use permissive licenses

## 🆘 Support

1. Check the troubleshooting section
2. Review Neo4j logs: `docker-compose logs neo4j`
3. Test individual components with the CLI status command
4. Use the Jupyter notebook for debugging

## 📊 Sample Output

```
🔍 Query: "Portfolio Punkte Bewertung"
==================================================

1. 📝 Portfolio Punkte (Score: 0.892)
   Post ID: 1146802
   Content: Bei der Portfoliopunkte Bewertung steht unten Kurs gesamt und Portfolio Punkte final welches gilt denn jetzt ?

2. 📝 Re: Portfolio Punkte (Score: 0.756)
   Post ID: 1147508
   Content: Wir haben angekündigt , dass die Aktivitäten in ISIS nicht aktualisiert werden. Prüfen Sie, ob und welche Portfoliopunkte(!) eingetragen sind...

Graph Context: 2 expanded results with thread relationships
```

---

**Ready to explore your forum data with GraphRAG!** 🚀

Start with: `python cli.py build forum_data.json`