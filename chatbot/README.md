# Tromsø Municipality RAG Chatbot

This project implements an **AI-powered chatbot** that can answer user questions based on content scraped from the official Tromsø Municipality website: [https://tromso.kommune.no](https://tromso.kommune.no).  
It uses **Retrieval-Augmented Generation (RAG)** with a vector database (FAISS) and a lightweight open LLM (Flan-T5-base) to provide factual, context-aware answers.

---

## 📚 Overview

**Main features**
- Automatically scrapes and indexes allowed public content from `tromso.kommune.no`
- Stores embeddings in a FAISS vector database for fast semantic retrieval
- Generates human-like, context-grounded answers using **Flan-T5-base**
- Includes a simple **Flask web interface** for interactive Q&A
- Displays **citations (URLs)** and **latency (response time)** for evaluation
- Fully containerized with a lightweight **Dockerfile**

**Core technologies**
| Component | Technology | Purpose |
|------------|-------------|----------|
| Web scraping | BeautifulSoup, requests | Collect website text data |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | Semantic vector encoding |
| Vector database | FAISS | Fast similarity search |
| LLM | google/flan-t5-base (Hugging Face) | Answer generation |
| Framework | LangChain + Flask | RAG orchestration & web app |
| Containerization | Docker | Portable runtime environment |

---

## ⚙️ Requirements

### Python environment
- Python 3.10+
- Recommended: virtual environment (`venv` or `conda`)

Install dependencies manually if not using Docker:
```bash
pip install -r requirements.txt
```

> Most important libraries:
> - flask
> - requests
> - beautifulsoup4
> - faiss-cpu
> - langchain
> - langchain_huggingface
> - transformers
> - sentence-transformers
> - torch

---

## 🧩 Project Structure

```
project/
│
├── app.py                 # Flask app serving the chatbot API and UI
├── ingest.py              # Scrapes Tromsø Kommune website and builds FAISS index
├── requirements.txt       # Python dependencies
├── Dockerfile             # Container configuration (Python 3.10-slim base)
├── templates/
│   └── index.html         # Front-end chat interface (English)
├── faiss_index/           # Generated embeddings (created after ingestion)
└── README.md              # This file
```

---

## 🚀 How to Run Locally (without Docker)

### 1. Prepare the environment
```bash
python -m venv .venv
source .venv/bin/activate        # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Build the FAISS index
This step scrapes the allowed pages of the Tromsø Municipality website and builds embeddings.
```bash
python ingest.py
```
You should see messages like:
```
[ok] https://tromso.kommune.no/helse-og-omsorg  (#1)
Split into 120 chunks.
Saved FAISS index to: faiss_index/
```

### 3. Start the chatbot
```bash
python app.py
```

### 4. Test in your browser
Open **http://localhost:5000**  
Ask questions such as:
- "How can I apply for kindergarten?"
- "What are Tromsø’s waste collection services?"
- "Who to contact for emergency healthcare?"

The chatbot will respond in **English**, cite its **sources**, and display **response latency**.

---

## 🐳 Run Using Docker (Recommended)
### ingest.py have to be run before docker build!! 
### 1. Build the Docker image
```bash
docker build -t rag-tromso:latest .
```

### 2. Run the container
```bash
docker run -it --rm -p 5000:5000 rag-tromso:latest
```

### 3. Access the chatbot
Go to [http://localhost:5000](http://localhost:5000)

### 4. Health check
Confirm readiness:
```bash
curl http://localhost:5000/health
```
Expected output:
```json
{"status":"ok"}
```

---

## 🧪 Evaluation

For your report, include these metrics:

| Metric | How to measure | Description |
|--------|----------------|-------------|
| **Accuracy** | Manually verify answers vs. source pages | % of correct factual responses |
| **Relevance** | Subjective 1–5 scale | How well each response fits the query |
| **Latency** | Returned as `latency_sec` | Total time per request (retrieval + generation) |

Example response (from the API or browser):
```json
{
  "answer": "You can apply for kindergarten through the municipal portal. Applications are handled by Tromsø Municipality.",
  "latency_sec": 1.204,
  "sources": [
    {"url": "https://tromso.kommune.no/barnehage", "title": "Barnehage (Kindergarten)"}
  ]
}
```

---

## 🧰 Tips & Notes

- **Respects robots.txt** — the ingestion script automatically checks and skips disallowed pages.
- **Polite crawling** — 1.5s delay and User-Agent header used.
- **English-only output** — the prompt explicitly enforces English answers.
- **Lightweight model** — runs on CPU or a single 40GB VRAM GPU.
- **Citations included** — retrieved document titles/URLs are returned in each response.
- **Latency displayed** — measured for each query and shown in UI.
- **Code clarity** — modular structure with inline comments.

---

## 🧩 Example Workflow Summary

```bash
# (1) Build index
python ingest.py

# (2) Start Flask app
python app.py

# (3) Ask a question
curl -X POST http://localhost:5000/query   -H "Content-Type: application/json"   -d '{"question":"How to contact the health department?"}'
```

---

## 📄 License / Acknowledgements

This chatbot uses open-source components under permissive licenses:
- [Hugging Face Transformers](https://github.com/huggingface/transformers)
- [LangChain](https://github.com/langchain-ai/langchain)
- [Sentence-Transformers](https://www.sbert.net/)
- [FAISS](https://github.com/facebookresearch/faiss)

Website content © Tromsø Municipality — used only for educational purposes (UiT assignment).

---

## ✍️ Authors

**UiT Chatbot Group — Assignment 2 (Autumn 2025)**  
Course: *AI & Intelligent Systems Engineering*  
University of Tromsø – The Arctic University of Norway
