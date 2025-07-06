import torch
from langchain_community.embeddings import HuggingFaceEmbeddings
from sqlalchemy import text
from sqlalchemy.orm import Session

embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": "cuda" if torch.cuda.is_available() else "cpu"},
)

def get_query_embedding(text_query: str) -> list:
    return embedding_model.embed_query(text_query)


def hybrid_search(
    session: Session,
    query: str,
    top_k=5,
    vector_weight=0.7,
    text_weight=0.3,
    collection_id: str | None = None,
):
    query_vec = get_query_embedding(query)
    vector_clause = f"(content_vector <=> '[{','.join(map(str, query_vec))}]'::vector)"

    sql = f"""
        SELECT *,
            {vector_weight} * (1 - {vector_clause}) + {text_weight} * ts_rank(content_tsv, plainto_tsquery(:q)) AS final_score
        FROM documents
        WHERE (:c_id IS NULL OR collection_id = :c_id) AND
              (content_tsv @@ plainto_tsquery(:q))
        ORDER BY final_score DESC
        LIMIT :k
    """
    result = session.execute(
        text(sql),
        {"q": query, "k": top_k, "c_id": collection_id},
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
    session: Session, query: str, collection_id: str | None = None, top_k: int = 5
) -> tuple[str, set[str]]:
    matches = hybrid_search(session, query, top_k=top_k, collection_id=collection_id)
    contexts = []
    sources = set()
    for row in matches:
        contexts.append(row.content)
        breakpoint()
        sources.add(build_source_url(row.collection_id, row.source))
    combined_context = "\n".join(contexts)
    return combined_context, sources
