# setup.sh - Neo4j Setup Script
#!/bin/bash

echo "🚀 Setting up Forum GraphRAG System"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Download German spaCy model
echo "🇩🇪 Installing German language model..."
python -m spacy download de_core_news_sm

# Check if Neo4j is running
echo "🔍 Checking Neo4j connection..."
python -c "
from neo4j import GraphDatabase
try:
    driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'password'))
    with driver.session() as session:
        session.run('RETURN 1')
    print('✅ Neo4j connection successful!')
    driver.close()
except Exception as e:
    print('❌ Neo4j connection failed:', e)
    print('Please ensure Neo4j is running on bolt://localhost:7687')
    print('Default credentials: neo4j/password')
"

echo "✅ Setup complete!"
