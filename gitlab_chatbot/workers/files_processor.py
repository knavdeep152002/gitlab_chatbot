# scraper/file_processor.py

import logging
import re
from celery import Celery
from typing import Dict, List

from langchain_text_splitters import RecursiveCharacterTextSplitter
from gitlab_chatbot.settings import config
from gitlab_chatbot.models.document_db import Document, Checkpoint
from gitlab_chatbot.db.crud_helper import document_crud, checkpoint_crud
from gitlab_chatbot.workers.gitlab_utils import get_file_content
from gitlab_chatbot.workers.schema import CheckpointState

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
BATCH_SIZE = 50
MAX_WORKERS = 4
CHUNK_SIZE = 1000
EMBED_BATCH_SIZE = 32

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
    keep_separator=True,
)

whitespace_pattern = re.compile(r"[ \t\r\n]+")

app = Celery("file_processor", broker=config.celery_broker_url, queue="file_processor")

def clean_text(text: str) -> str:
    return whitespace_pattern.sub(" ", text).strip()

def chunk_content(content: str, source: str, collection_id: str) -> List[Dict]:
    cleaned_content = clean_text(content)
    chunks = text_splitter.split_text(cleaned_content)
    return [
        {
            "collection_id": collection_id,
            "source": source,
            "chunk_index": i,
            "content": chunk,
            "document_metadata": {"length": len(chunk)},
        }
        for i, chunk in enumerate(chunks)
    ]

@app.task(name="process_file", opts={"max_retries": 3, "retry_backoff": True, "queue": "file_processor"})
def process_file(project_id: int, file_path: str, commit_sha: str, collection_id: str):
    logger.info(f"Processing file: {file_path} for collection: {collection_id}")
    try:
        existing_checkpoint = checkpoint_crud.get_resource(
            resource_id=None,
            where=[
                Checkpoint.commit_id == commit_sha,
                Checkpoint.file_path == file_path,
            ],
        )
        if existing_checkpoint and existing_checkpoint["state"] in [
            CheckpointState.PROCESSED,
            CheckpointState.EMBEDDED,
        ]:
            logger.info(f"Skipping already processed file: {file_path}")
            return

        content = get_file_content(project_id, file_path, commit_sha)
        chunks = chunk_content(content, file_path, collection_id)

        document_crud.delete_resource(
            resource_id=None,
            where=[
                Document.source == file_path,
                Document.collection_id == collection_id,
            ],
        )
        for chunk in chunks:
            document_crud.create_resource(chunk)
            app.send_task(
                "embed_chunk",
                args=[chunk["source"], chunk["chunk_index"], chunk["collection_id"]],
                queue="embedding",
            )

        checkpoint_data = {
            "commit_id": commit_sha,
            "file_path": file_path,
            "state": CheckpointState.PROCESSED,
        }
        
        if existing_checkpoint:
            checkpoint_crud.update_resource(
                data=checkpoint_data,
                where=[
                    Checkpoint.commit_id == commit_sha,
                    Checkpoint.file_path == file_path,
                ],
            )
        else:
            checkpoint_crud.create_resource(checkpoint_data)

        logger.info(f"✅ Completed processing file: {file_path}")

    except Exception as e:
        logger.error(f"❌ Error processing file {file_path}: {e}")
        checkpoint_crud.create_resource(
            {
                "commit_id": commit_sha,
                "file_path": file_path,
                "state": "ERROR",
                "error_message": str(e),
            }
        )
