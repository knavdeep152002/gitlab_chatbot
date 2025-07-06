import logging
from typing import List
from celery import Celery
from langchain_community.embeddings import HuggingFaceEmbeddings
from sqlalchemy.sql import text
from torch import cuda

from gitlab_chatbot.settings import config
from gitlab_chatbot.db.crud_helper import document_crud, checkpoint_crud
from gitlab_chatbot.models.document_db import Document, Checkpoint
from gitlab_chatbot.workers.schema import CheckpointState

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

app = Celery(
    "embed_chunk_worker",
    broker=config.celery_broker_url,
)
app.conf.task_acks_late = True
app.conf.worker_prefetch_multiplier = 1
app.conf.task_track_started = True

DEVICE = "cuda" if cuda.is_available() else "cpu"

# --- Setup embedding model ---
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"device": DEVICE},
)


@app.task(name="embed_chunk", bind=True, max_retries=3, default_retry_delay=60)
def embed_chunk(self, source: str, chunk_index: int, collection_id: str):
    logger.info(f"🔢 Embedding chunk {chunk_index} from {source}")

    try:
        chunk = document_crud.get_resource(
            resource_id=None,
            where=[
                Document.source == source,
                Document.chunk_index == chunk_index,
                Document.collection_id == collection_id,
            ],
        )

        if not chunk:
            logger.warning(f"⚠️ Chunk not found: {source}:{chunk_index}")
            return

        content = chunk["content"]
        vector = embedding_model.embed_documents([content])[0]

        # Update vector and tsv
        document_crud.update_resource(
            data={
                "content_vector": vector,
                "content_tsv": text("to_tsvector('english', content)"),
            },
            where=[
                Document.source == source,
                Document.chunk_index == chunk_index,
                Document.collection_id == collection_id,
            ],
        )

        checkpoint_crud.update_resource(
            data={"state": CheckpointState.EMBEDDED},
            where=[
                Checkpoint.file_path == source,
                Checkpoint.state != "DELETED",
            ],
        )

        logger.info(f"✅ Embedded: {source}:{chunk_index}")

    except Exception as e:
        logger.error(f"❌ Embedding failed for {source}:{chunk_index}: {e}")
        checkpoint_crud.update_resource(
            data={"state": CheckpointState.ERROR, "error_message": str(e)},
            where=[Checkpoint.file_path == source],
        )
        self.retry(exc=e)
