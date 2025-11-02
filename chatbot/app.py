import os
import time
from typing import List, Dict, Optional
from flask import Flask, render_template, request, jsonify

# LangChain / Vector store / Embeddings
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# Prompting & Chains
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

# Hugging Face generation
from transformers import pipeline, AutoTokenizer
from langchain_huggingface import HuggingFacePipeline


app = Flask(__name__)
db: Optional[FAISS] = None
llm = None


# -----------------------------
# Configuration
# -----------------------------
FAISS_DIR = "faiss_index"

# Must match ingest.py
EMBED_MODEL = "intfloat/multilingual-e5-base"
GEN_MODEL = "google/flan-t5-base"

# Model / context settings
MAX_TOKENS = 2048            # input token limit (for truncation)
MAX_CONTEXT_CHARS = 32000    # allow more Wikipedia context text
GEN_MAX_NEW_TOKENS = 1024    # allow much longer generated answers
RETRIEVAL_K = 6
FETCH_K = 50
MMR_LAMBDA = 0.3


# -----------------------------
# Custom pipeline wrapper
# -----------------------------
class TruncatingHuggingFacePipeline(HuggingFacePipeline):
    """Wrapper to truncate overly long prompts before calling the generation pipeline."""
    def __init__(self, pipeline, tokenizer, max_tokens: int):
        super().__init__(pipeline=pipeline)
        self._tokenizer = tokenizer
        self._max_tokens = max_tokens

    def __call__(self, prompt, stop=None):
        def _truncate(text: str) -> str:
            input_ids = self._tokenizer.encode(
                text, truncation=True, max_length=self._max_tokens
            )
            return self._tokenizer.decode(input_ids)

        if isinstance(prompt, list):
            truncated_list = []
            for item in prompt:
                if isinstance(item, dict):
                    prompt_text = item.get("text") or item.get("inputs") or item.get("prompt") or ""
                else:
                    prompt_text = str(item)
                truncated_list.append(_truncate(prompt_text))
            return super().__call__(truncated_list, stop=stop)
        elif isinstance(prompt, dict):
            prompt_text = prompt.get("text") or prompt.get("inputs") or prompt.get("prompt") or ""
            return super().__call__(_truncate(prompt_text), stop=stop)
        else:
            return super().__call__(_truncate(str(prompt)), stop=stop)


# -----------------------------
# Initialization
# -----------------------------
def initialize_components() -> Optional[str]:
    """Load embeddings, FAISS index, and initialize generation model."""
    global db, llm
    try:
        if not os.path.exists(FAISS_DIR):
            return f"FAISS index not found in ./{FAISS_DIR}. Run `python ingest.py` first."

        print("🔹 Loading embeddings…")
        embeddings = HuggingFaceEmbeddings(
            model_name=EMBED_MODEL,
            encode_kwargs={"batch_size": 32, "normalize_embeddings": True}
        )

        print("🔹 Loading FAISS index…")
        db = FAISS.load_local(FAISS_DIR, embeddings, allow_dangerous_deserialization=True)
        print(f"✅ FAISS index loaded ({len(db.index_to_docstore_id)} vectors).")

        print("🔹 Initializing generation model…")
        tokenizer = AutoTokenizer.from_pretrained(GEN_MODEL)
        generator = pipeline(
            "text2text-generation",
            model=GEN_MODEL,
            max_new_tokens=GEN_MAX_NEW_TOKENS,  # extended generation length
            temperature=0.5,                     # slightly more natural and descriptive
            top_p=0.95
        )
        llm = TruncatingHuggingFacePipeline(generator, tokenizer, MAX_TOKENS)
        print("✅ LLM initialized successfully.")
        return None

    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Initialization error: {e}"


# -----------------------------
# Prompt and helper utilities
# -----------------------------
def build_prompt() -> PromptTemplate:
    """Create the question-answering prompt template."""
    template = """You are a knowledgeable assistant that answers user questions using verified Wikipedia information.

Instructions:
- Always answer in the same language as the user's question.
- Base your response ONLY on the provided Wikipedia context.
- If the context does not contain the answer, say "I don't know."
- Provide a detailed, well-structured, and informative answer.
- When possible, include explanations, examples, dates, or background details.
- Answer in full, but simple sentences.

Context:
{context}

User Question: {user_query}

Answer:"""
    return PromptTemplate(template=template, input_variables=["context", "user_query"])


def serialize_sources(docs) -> List[Dict[str, str]]:
    """Extract URLs and titles from document metadata."""
    seen = set()
    results: List[Dict[str, str]] = []
    for d in docs:
        url = d.metadata.get("source", "")
        title = d.metadata.get("title", "")
        if url and url not in seen:
            results.append({"url": url, "title": title})
            seen.add(url)
    return results


def join_context(docs) -> str:
    """Concatenate document texts, truncated by character limit."""
    context = "\n\n".join(d.page_content for d in docs if getattr(d, "page_content", None))
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS]
    return context


# -----------------------------
# Routes
# -----------------------------
@app.route("/health", methods=["GET"])
def health():
    ok = (db is not None) and (llm is not None)
    return jsonify({"status": "ok" if ok else "not_ready"}), (200 if ok else 503)


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/query", methods=["POST"])
def query():
    global db, llm
    try:
        if db is None or llm is None:
            return jsonify({"error": "System not initialized. Check logs."}), 500

        payload = request.get_json(silent=True) or {}
        user_query = (payload.get("question") or "").strip()
        if not user_query:
            return jsonify({"error": "No question provided."}), 400

        t0 = time.time()

        # Retrieval (MMR with fallback)
        try:
            docs = db.max_marginal_relevance_search(
                f"query: {user_query}", k=RETRIEVAL_K, fetch_k=FETCH_K, lambda_mult=MMR_LAMBDA
            )
        except Exception:
            docs = db.similarity_search(f"query: {user_query}", k=RETRIEVAL_K)

        if not docs:
            latency = round(time.time() - t0, 3)
            return jsonify({
                "answer": "I don't know. I could not find relevant information in the indexed Wikipedia content.",
                "latency_sec": latency,
                "sources": []
            })

        context = join_context(docs)
        prompt = build_prompt()
        chain = LLMChain(prompt=prompt, llm=llm)

        # Run LLM
        answer = chain.run({"context": context, "user_query": user_query}).strip()
        latency = round(time.time() - t0, 3)
        sources = serialize_sources(docs)

        token_count = len(llm._tokenizer.encode(context + user_query))
        print(f"🔹 Query processed. Tokens: {token_count}, Latency: {latency}s")

        if not answer:
            answer = "I don't know."

        return jsonify({
            "answer": answer,
            "latency_sec": latency,
            "sources": sources
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# -----------------------------
# Entry point
# -----------------------------
if __name__ == "__main__":
    err = initialize_components()
    if err:
        print(err)
    else:
        print("🚀 Wikipedia chatbot ready at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)