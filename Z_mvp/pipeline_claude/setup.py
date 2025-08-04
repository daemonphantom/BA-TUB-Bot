
# setup.py
from setuptools import setup, find_packages

setup(
    name="forum-graphrag",
    version="0.1.0",
    description="GraphRAG system for forum data analysis",
    packages=find_packages(),
    install_requires=[
        "sentence-transformers>=2.2.2",
        "neo4j>=5.0.0",
        "numpy>=1.21.0",
        "scikit-learn>=1.0.0",
        "spacy>=3.4.0",
        "networkx>=2.8.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "full": ["tiktoken>=0.4.0"],
    },
    python_requires=">=3.8",
)
