import logging
import torch
from langchain_community.embeddings import HuggingFaceEmbeddings
from sqlalchemy import text
from sqlalchemy.orm import Session
from gitlab_chatbot.settings import config

logger = logging.getLogger(__name__)

embedding_model = HuggingFaceEmbeddings(
    model_name=config.huggingface_model,
    model_kwargs={"device": "cuda" if torch.cuda.is_available() else "cpu"},
)


def get_query_embedding(text_query: str) -> list:
    return embedding_model.embed_documents([text_query])[0]


def has_fulltext_index(session: Session) -> bool:
    sql = """
    SELECT COUNT(*) FROM pg_indexes
    WHERE tablename = 'documents' AND indexname LIKE '%tsv%'
    """
    count = session.execute(text(sql)).scalar()
    return (count is not None) and (count > 0)


def hybrid_search(
    session: Session,
    query: str,
    top_k=10,
    vector_weight=0.7,
    text_weight=0.3,
):
    query_vec = get_query_embedding(query)
    vector_str = f"[{','.join(map(str, query_vec))}]"

    if has_fulltext_index(session):
        logger.info("🔍 Using hybrid fulltext + vector search")
        sql = f"""
            SELECT *,
                {vector_weight} * (1 - (content_vector <=> :vec)::float) +
                {text_weight} * COALESCE(ts_rank(content_tsv, plainto_tsquery(:q)), 0) AS final_score
            FROM documents
            WHERE (content_tsv @@ plainto_tsquery(:q))
            ORDER BY final_score DESC
            LIMIT :k
        """
        result = session.execute(
            text(sql),
            {"q": query, "vec": vector_str, "k": top_k},
        )
    else:
        logger.warning("Fulltext index not found. Falling back to vector-only search.")
        sql = """
            SELECT *,
                1 - (content_vector <=> :vec)::float AS final_score
            FROM documents
            WHERE content_vector IS NOT NULL
            ORDER BY final_score DESC
            LIMIT :k
        """
        result = session.execute(
            text(sql),
            {"vec": vector_str, "k": top_k},
        )

    return result.fetchall()


def build_source_url(collection_id: str, file_path: str) -> str:
    if collection_id == "handbook":
        relative_path = file_path.removeprefix("content/handbook/").removesuffix(".md")
        url_path = (
            relative_path.replace(".md", "").replace("_index", "").replace("README", "")
        )
        return f"https://handbook.gitlab.com/{url_path}"
    elif collection_id == "direction":
        relative_path = file_path.removeprefix("source/direction/").removesuffix(".md")
        url_path = (
            relative_path.replace(".md", "").replace("_index", "").replace("README", "")
        )
        return f"https://about.gitlab.com/direction/{url_path}"
    else:
        return file_path


def generate_rag_context(
    session: Session, query: str, top_k: int = 5
) -> tuple[str, set[str]]:
    matches = hybrid_search(session, query, top_k=top_k)
    contexts = []
    sources = set()
    for row in matches:
        contexts.append(row.content)
        sources.add(build_source_url(row.collection_id, row.source))
    combined_context = "\n".join(contexts)
    return combined_context, sources
