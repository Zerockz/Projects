# ingest.py
# Wikipedia Category-based ingestion for FAISS RAG
# Collects limited pages under "Category:Norway" via the official Wikipedia API.

import os
import time
import wikipediaapi
from tqdm import tqdm
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS


# -----------------------
# Config
# -----------------------
CATEGORY_NAME = "Category:Norway"   # Root Wikipedia category
LANG = "en"
MAX_DEPTH = 2                       # 1=direct pages only, 2=include subcategories
MAX_ARTICLES = 1000                   # Limit total articles for faster ingestion
FAISS_DIR = "faiss_index"

# Embedding model (must match app.py)
EMBED_MODEL = "intfloat/multilingual-e5-base"

# Chunking
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150


# -----------------------
# Category traversal with limit
# -----------------------
def get_category_members(category_page, level=0, max_depth=2, limit=200, collected=None):
    """
    Recursively collects Wikipedia articles from a category (up to 'limit').
    """
    if collected is None:
        collected = []

    for c in category_page.categorymembers.values():
        # Stop if we reached the limit
        if len(collected) >= limit:
            return collected

        if c.ns == wikipediaapi.Namespace.MAIN:
            text = c.text
            if len(text) < 400:
                continue  # skip short stubs
            collected.append(Document(
                page_content=text,
                metadata={"source": c.fullurl, "title": c.title}
            ))

        elif c.ns == wikipediaapi.Namespace.CATEGORY and level < max_depth:
            get_category_members(c, level + 1, max_depth, limit, collected)

    return collected


# -----------------------
# Build FAISS index
# -----------------------
def build_faiss_index(docs):
    if not docs:
        raise RuntimeError("No documents collected. Aborting FAISS build.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.split_documents(docs)
    print(f"Split into {len(chunks)} chunks.")

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        encode_kwargs={"batch_size": 32, "normalize_embeddings": True},
    )

    print("Building FAISS index…")
    BATCH = 128
    texts = [f"passage: {c.page_content}" for c in chunks]
    metas = [c.metadata for c in chunks]

    db = None
    with tqdm(total=len(texts), desc="Embedding & indexing", unit="chunk") as pbar:
        for i in range(0, len(texts), BATCH):
            t_batch = texts[i : i + BATCH]
            m_batch = metas[i : i + BATCH]
            if db is None:
                db = FAISS.from_texts(t_batch, embedding=embeddings, metadatas=m_batch)
            else:
                db.add_texts(t_batch, metadatas=m_batch, embedding=embeddings)
            pbar.update(len(t_batch))

    os.makedirs(FAISS_DIR, exist_ok=True)
    db.save_local(FAISS_DIR)
    print(f"✅ FAISS index saved to: {FAISS_DIR}/")


# -----------------------
# Main entry
# -----------------------
def main():
    print(f"🔍 Fetching Wikipedia category: {CATEGORY_NAME} (lang={LANG})")
    wiki = wikipediaapi.Wikipedia(
        language=LANG,
        extract_format=wikipediaapi.ExtractFormat.WIKI,
        user_agent="UiT-RAGBot/1.0 (elmi@example.com)"  # change contact info
    )

    start = time.time()
    category = wiki.page(CATEGORY_NAME)
    if not category.exists():
        raise RuntimeError(f"Category not found: {CATEGORY_NAME}")

    docs = get_category_members(category, level=0, max_depth=MAX_DEPTH, limit=MAX_ARTICLES)
    print(f"Collected {len(docs)} articles from {CATEGORY_NAME} (depth={MAX_DEPTH})")

    build_faiss_index(docs)
    print(f"✅ Done in {round(time.time() - start, 2)} sec.")


if __name__ == "__main__":
    main()
