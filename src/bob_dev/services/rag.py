"""rag.py

RAG job for bob_dev:
  - Fetches official documentation for the detected framework from the web.
  - Splits, embeds, and persists a FAISS vector index to ~/.bob_dev/rag_cache/.
  - Exposes retrieve_rag_context() to return relevant chunks as a plain string.

The index is cached on disk keyed by framework name so subsequent runs are
instant.  Pass force_rebuild=True to re-fetch and re-index.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from langchain_community.document_loaders import WebBaseLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


# ---------------------------------------------------------------------------
# Framework → documentation URL mapping
# ---------------------------------------------------------------------------

FRAMEWORK_DOCS: dict[str, list[str]] = {
    "Django REST Framework": [
        "https://www.django-rest-framework.org/",
        "https://www.django-rest-framework.org/api-guide/views/",
        "https://www.django-rest-framework.org/api-guide/serializers/",
    ],
    "Django": [
        "https://docs.djangoproject.com/en/stable/intro/overview/",
        "https://docs.djangoproject.com/en/stable/topics/db/models/",
    ],
    "FastAPI": [
        "https://fastapi.tiangolo.com/",
        "https://fastapi.tiangolo.com/tutorial/first-steps/",
    ],
    "Flask": [
        "https://flask.palletsprojects.com/en/latest/quickstart/",
    ],
    "React": [
        "https://react.dev/learn",
        "https://react.dev/reference/react",
    ],
    "Next.js": [
        "https://nextjs.org/docs",
    ],
    "Vue.js": [
        "https://vuejs.org/guide/introduction",
    ],
    "Angular": [
        "https://angular.dev/overview",
    ],
    "NestJS": [
        "https://docs.nestjs.com/",
        "https://docs.nestjs.com/controllers",
    ],
    "Express.js": [
        "https://expressjs.com/en/starter/hello-world.html",
        "https://expressjs.com/en/guide/routing.html",
    ],
    "Spring Boot": [
        "https://docs.spring.io/spring-boot/docs/current/reference/html/",
    ],
    "Svelte": [
        "https://svelte.dev/docs",
    ],
    "Nuxt.js": [
        "https://nuxt.com/docs/getting-started/introduction",
    ],
}

_CACHE_DIR = Path.home() / ".bob_dev" / "rag_cache"
_SPLITTER = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_embeddings(agent: str, grok_api_key: str, openai_api_key: str) -> OpenAIEmbeddings:
    if agent == "GROK":
        return OpenAIEmbeddings(
            openai_api_key=grok_api_key,
            openai_api_base="https://api.x.ai/v1",
            model="text-embedding-3-small",
        )
    return OpenAIEmbeddings(openai_api_key=openai_api_key, model="text-embedding-3-small")


def _cache_path(framework: str) -> Path:
    slug = hashlib.md5(framework.encode()).hexdigest()[:8]
    return _CACHE_DIR / f"{slug}_faiss"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_rag_index(
    framework: str,
    agent: str,
    grok_api_key: str,
    openai_api_key: str,
    force_rebuild: bool = False,
) -> FAISS | None:
    """Fetch docs for *framework*, embed them, and persist a FAISS index.

    Returns the FAISS store, or None if no documentation URLs are mapped for
    the framework.  Loads from disk cache on subsequent calls unless
    force_rebuild=True.
    """
    urls = FRAMEWORK_DOCS.get(framework)
    if not urls:
        return None

    emb = _build_embeddings(agent, grok_api_key, openai_api_key)
    cache = _cache_path(framework)

    if cache.exists() and not force_rebuild:
        return FAISS.load_local(str(cache), emb, allow_dangerous_deserialization=True)

    docs = WebBaseLoader(urls).load()
    chunks = _SPLITTER.split_documents(docs)

    store = FAISS.from_documents(chunks, emb)
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    store.save_local(str(cache))
    return store


def retrieve_rag_context(
    framework: str,
    query: str,
    agent: str,
    grok_api_key: str,
    openai_api_key: str,
    k: int = 5,
) -> str:
    """Return the top-k relevant documentation chunks for *query* as a string.

    Returns an empty string if the framework has no mapped documentation or if
    the index cannot be built (e.g. network error, missing embedding key).
    """
    try:
        store = build_rag_index(framework, agent, grok_api_key, openai_api_key)
        if store is None:
            return ""
        results = store.similarity_search(query, k=k)
        return "\n\n---\n\n".join(doc.page_content for doc in results)
    except Exception:
        return ""
