from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class Message(BaseModel):
    """Message model for conversation history"""
    role: str = Field(..., description="Role of the message sender (system, user, assistant)")
    content: str = Field(..., description="Content of the message")
    tool_call_id: Optional[str] = Field(None, description="ID of tool call if applicable")
    sequence_order: Optional[int] = Field(None, description="Order of message in conversation")
    created_at: Optional[datetime] = Field(None, description="Timestamp when message was created")

    class Config:
        schema_extra = {
            "example": {
                "role": "user",
                "content": "How do I configure GitLab CI/CD pipelines?",
                "tool_call_id": None,
                "sequence_order": 2,
                "created_at": "2025-07-06T17:47:24.660597+00:00"
            }
        }

class ConversationResponse(BaseModel):
    """Response model for conversation retrieval"""
    conversation_id: str = Field(..., description="Unique identifier for the conversation")
    messages: List[Message] = Field(..., description="List of messages in the conversation")

    class Config:
        schema_extra = {
            "example": {
                "conversation_id": "a542db3f-0e80-4d34-8574-982966e038c6",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a helpful assistant...",
                        "tool_call_id": None,
                        "sequence_order": 1
                    },
                    {
                        "role": "user", 
                        "content": "How do I configure GitLab CI/CD?",
                        "tool_call_id": None,
                        "sequence_order": 2
                    }
                ]
            }
        }

class MessageRequest(BaseModel):
    """Request model for sending messages"""
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID to continue existing conversation")
    message: str = Field(..., min_length=1, max_length=10000, description="The user's message")

    class Config:
        schema_extra = {
            "example": {
                "conversation_id": "a542db3f-0e80-4d34-8574-982966e038c6",
                "message": "How do I configure GitLab CI/CD pipelines?"
            }
        }

class MessageResponse(BaseModel):
    """Response model for message sending"""
    conversation_id: str = Field(..., description="Unique identifier for the conversation")
    response: str = Field(..., description="The assistant's response")
    tool_used: Optional[str] = Field(None, description="Name of tool used to generate response")
    tool_result: Optional[str] = Field(None, description="Raw result from tool execution")
    sources: Optional[List[str]] = Field(None, description="List of sources used in the response")
    error: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "conversation_id": "a542db3f-0e80-4d34-8574-982966e038c6",
                "response": "GitLab CI/CD pipelines are configured using a .gitlab-ci.yml file[[1]](https://docs.gitlab.com/ee/ci/yaml/)...",
                "tool_used": "hybrid_gitlab_search",
                "tool_result": "GitLab CI/CD allows you to...",
                "sources": ["https://docs.gitlab.com/ee/ci/yaml/", "https://handbook.gitlab.com/ci/"]
            }
        }

class ConversationCreateResponse(BaseModel):
    """Response model for conversation creation"""
    conversation_id: str = Field(..., description="Unique identifier for the newly created conversation")

    class Config:
        schema_extra = {
            "example": {
                "conversation_id": "a542db3f-0e80-4d34-8574-982966e038c6"
            }
        }

class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")

    class Config:
        schema_extra = {
            "example": {
                "error": "Conversation not found",
                "detail": "No conversation exists with the provided ID"
            }
        }