from gitlab_chatbot.db import CRUDCapability
from gitlab_chatbot.models.document_db import Document, Checkpoint, CommitTracker
from gitlab_chatbot.models.chat import Conversation, Message


class DocumentCRUD(CRUDCapability[Document]):
    resource_db = Document


class CheckpointCRUD(CRUDCapability[Checkpoint]):
    resource_db = Checkpoint


class CommitTrackerCRUD(CRUDCapability[CommitTracker]):
    resource_db = CommitTracker


class ConversationSessionCRUD(CRUDCapability[Conversation]):
    resource_db = Conversation


class ChatMessageCRUD(CRUDCapability[Message]):
    resource_db = Message


conversation_session_crud = ConversationSessionCRUD(Conversation)
chat_message_crud = ChatMessageCRUD(Message)
document_crud = DocumentCRUD(Document)
checkpoint_crud = CheckpointCRUD(Checkpoint)
commit_tracker_crud = CommitTrackerCRUD(CommitTracker)
