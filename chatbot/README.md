Wikipedia RAG Chatbot
A Flask-based Retrieval-Augmented Generation (RAG) chatbot that answers questions using Wikipedia content about Norway. The system uses FAISS for vector similarity search and Hugging Face models for embeddings and text generation.
Overview
This project consists of three main components:

Data Ingestion (ingest.py) - Crawls Wikipedia categories and builds a FAISS vector index
Web Application (app.py) - Flask server that handles user queries with RAG pipeline
Evaluation (evaluate.py) - Tests the chatbot's accuracy and response quality

Features

Multilingual Support: Uses intfloat/multilingual-e5-base for embeddings
Smart Retrieval: Implements Maximum Marginal Relevance (MMR) for diverse, relevant results
Context-Aware: Generates answers based only on retrieved Wikipedia content
Source Attribution: Returns Wikipedia URLs for fact-checking
Truncation Handling: Automatically manages long contexts to prevent token overflow

Installation
bashpip install flask langchain langchain-community langchain-huggingface \
    faiss-cpu transformers wikipediaapi tqdm
Usage
1. Build the Knowledge Base
bashpython ingest.py
This crawls Wikipedia's "Category:Norway" (up to 1000 articles, depth 2) and creates a FAISS index in ./faiss_index/.
2. Run the Chatbot
bashpython app.py
Access the web interface at http://localhost:5000
3. Query via API
bashcurl -X POST http://localhost:5000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the capital of Norway?"}'
4. Evaluate Performance
Create evaluation_questions.csv with columns: question, expected_answer
bashpython evaluate.py
Configuration
Key parameters in app.py and ingest.py:

MAX_ARTICLES = 1000 - Number of Wikipedia pages to index
RETRIEVAL_K = 6 - Documents retrieved per query
CHUNK_SIZE = 900 - Text chunk size for embeddings
GEN_MODEL = "google/flan-t5-base" - Generation model
MAX_DEPTH = 2 - Category traversal depth

Models Used

Embeddings: intfloat/multilingual-e5-base
Generation: google/flan-t5-base

API Endpoints

GET / - Web interface
GET /health - System status check
POST /query - Submit questions (JSON: {"question": "..."})

Response Format
json{
  "answer": "Oslo is the capital of Norway...",
  "latency_sec": 1.23,
  "sources": [
    {"url": "https://en.wikipedia.org/wiki/Oslo", "title": "Oslo"}
  ]
}
Notes

The system only answers based on indexed Wikipedia content
Responses are in the same language as the question
If information isn't found, it responds with "I don't know"
Modify CATEGORY_NAME in ingest.py to index different Wikipedia topics
