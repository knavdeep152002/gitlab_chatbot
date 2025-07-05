from gitlab_chatbot.db import CRUDCapability
from gitlab_chatbot.models.document_db import Document, Checkpoint, CommitTracker

class DocumentCRUD(CRUDCapability[Document]):
    resource_db = Document


class CheckpointCRUD(CRUDCapability[Checkpoint]):
    resource_db = Checkpoint


class CommitTrackerCRUD(CRUDCapability[CommitTracker]):
    resource_db = CommitTracker

document_crud = DocumentCRUD(Document)
checkpoint_crud = CheckpointCRUD(Checkpoint)
commit_tracker_crud = CommitTrackerCRUD(CommitTracker)
