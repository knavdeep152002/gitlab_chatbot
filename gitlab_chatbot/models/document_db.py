from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    JSON,
    Index,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector

from .base import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    collection_id = Column(String(100), nullable=False, index=True)  # handbook or direction_pages
    source = Column(String(2048), nullable=False, index=True)  # URL to handbook section
    chunk_index = Column(Integer, nullable=False)  # order of chunk within source
    content = Column(Text, nullable=False)
    content_vector = Column(Vector(1536), nullable=True)
    content_tsv = Column(TSVECTOR)  # PostgreSQL full-text index
    document_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("source", "chunk_index", name="uq_source_chunk"),
        Index("idx_vector_search", "content_vector", postgresql_using="ivfflat"),
        Index("idx_tsv_search", "content_tsv", postgresql_using="gin"),
    )


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id = Column(Integer, primary_key=True)
    commit_id = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    state = Column(
        String(50), nullable=False
    )  # FETCHED, INSERTED, EMBEDDING_PENDING, EMBEDDED, DELETED, ERROR
    error_message = Column(Text)
    last_updated = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("commit_id", "file_path", name="uq_commit_file"),
        Index("idx_checkpoint_state", "state"),
    )


class CommitTracker(Base):
    __tablename__ = "commit_tracker"

    id = Column(Integer, primary_key=True)
    project_id = Column(String(255), nullable=False, unique=True)
    last_commit_id = Column(String(255), nullable=False)
    last_commit_time = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=func.now(), onupdate=func.now()
    )
