from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Tuple
import uuid
import json
import logging
import re

from gitlab_chatbot.db.crud_helper import conversation_session_crud, chat_message_crud
from gitlab_chatbot.models.chat import Conversation, Message
from gitlab_chatbot.utils.hybrid_search import generate_rag_context
from gitlab_chatbot.settings import config
from gitlab_chatbot.routes.chatbot.schemas import (
    MessageRequest,
    MessageResponse,
    ConversationResponse,
    ConversationCreateResponse,
    ErrorResponse,
)

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()


# --- LangChain Tool Definition ---
@tool
def hybrid_gitlab_search(query: str) -> Dict[str, Any]:
    """
    Performs hybrid search on GitLab documentation when GitLab-specific information is needed.

    Use this tool when the user asks about:
    - GitLab features, functionality, or how-to questions
    - GitLab policies, procedures, or handbook information
    - GitLab direction, roadmap, or strategic information
    - Technical GitLab implementation details
    - Or any generic question which are not too generic but might be related to gitlab handbook

    Example:
    If asked about 'What are the consequences of not testing a Business Continuity Plan?', You can hit this it might be related to this,
    If asked how are you, whats the day today, whats the temperature etc, No need to hit this.

    Do NOT use this tool for:
    - General programming questions
    - Questions about other tools or platforms
    - Casual conversation or greetings
    - Follow-up questions that can be answered from previous context

    Args:
        query: The search query for GitLab documentation

    Returns:
        Dictionary containing search results and sources
    """
    if not query or not query.strip():
        return {"content": "", "sources": []}

    try:
        session = chat_message_crud.get_sync_session()
        context, sources = generate_rag_context(session, query)
        return {"content": context, "sources": list(sources)}
    except Exception as e:
        logger.error(f"Error in hybrid_gitlab_search: {e}", exc_info=True)
        return {"content": "", "sources": []}


# --- Agent Setup ---
SYSTEM_MESSAGE = """You are a helpful assistant for GitLab documentation and general questions.

For GitLab-related questions, you have access to a tool that can search GitLab documentation. Use this tool when users ask about GitLab features, policies, procedures, or technical implementation details.

For general questions or follow-up questions that don't require new GitLab information, you can answer directly using your existing knowledge and the conversation context.

IMPORTANT FORMATTING RULES:
1. Format your response in Markdown
2. For GitLab-specific answers using the search tool, include inline citations like: [[1]](https://example.com)
3. At the end of responses with citations, include a "## Sources" section with numbered links
4. For general questions, provide helpful answers without citations

CONVERSATION CONTEXT:
Pay attention to the conversation history to understand follow-up questions and maintain context. When a user says "explain more" or "tell me about that", refer to the previous messages to understand what they're referring to.

Example with citations:
GitLab supports group-level permissions[[1]](https://handbook.gitlab.com/permissions).

## Sources
[1] [GitLab Handbook: Permissions](https://handbook.gitlab.com/permissions)
"""

try:
    llm = ChatGoogleGenerativeAI(
        model=config.gemini_model,
        google_api_key=config.gemini_api_key,
        temperature=0.2,
        streaming=True,
    )

    # Create agent prompt with conversation history
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_MESSAGE),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    # Create agent
    tools = [hybrid_gitlab_search]
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

except Exception as e:
    logger.error(f"Error initializing agent: {e}", exc_info=True)
    raise


def format_sources_from_tool_result(tool_outputs: List[Dict]) -> Tuple[str, List[str]]:
    """
    Extract and format sources from tool outputs.

    Args:
        tool_outputs: List of tool output dictionaries

    Returns:
        Tuple of (sources_markdown, sources_list)
    """
    all_sources = []

    for output in tool_outputs:
        if isinstance(output, dict) and "sources" in output:
            sources = output["sources"]
            if isinstance(sources, list):
                all_sources.extend(sources)

    if not all_sources:
        return "", []

    # Remove duplicates while preserving order
    unique_sources = []
    seen = set()
    for source in all_sources:
        if source not in seen:
            unique_sources.append(source)
            seen.add(source)

    sources_markdown = "\n## Sources\n"
    for i, url in enumerate(unique_sources, 1):
        # Extract title from URL or use URL as title
        title = url.split("/")[-1].replace("-", " ").title()
        if not title:
            title = url
        sources_markdown += f"[{i}] [{title}]({url})\n"

    return sources_markdown, unique_sources


def get_conversation_history(conversation_id: str, limit: int = 10) -> List:
    """
    Get conversation history as LangChain messages.

    Args:
        conversation_id: ID of the conversation
        limit: Maximum number of messages to retrieve

    Returns:
        List of LangChain message objects
    """
    try:
        messages = chat_message_crud.list_resource(
            where=[Message.conversation_id == conversation_id],
            order_by=["sequence_order"],
            limit=limit * 2,  # Get more to account for system messages
        )

        history = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "system":
                continue  # Skip system messages for history
            elif role == "user":
                history.append(HumanMessage(content=content))
            elif role == "assistant":
                history.append(AIMessage(content=content))

        # Return last 'limit' messages (excluding current)
        return history[:-1] if len(history) > 0 else []

    except Exception as e:
        logger.error(f"Error getting conversation history: {e}", exc_info=True)
        return []


def get_next_sequence_order(conversation_id: str) -> int:
    """
    Get the next sequence order for messages in a conversation.

    Args:
        conversation_id: ID of the conversation

    Returns:
        Next sequence order number
    """
    try:
        messages = chat_message_crud.list_resource(
            where=[Message.conversation_id == conversation_id],
            order_by=["sequence_order"],
        )
        if not messages:
            return 1
        return max(msg.get("sequence_order", 0) for msg in messages) + 1
    except Exception as e:
        logger.error(f"Error getting next sequence order: {e}", exc_info=True)
        return 1


def create_system_message(conversation_id: str) -> None:
    """
    Create initial system message for a new conversation.

    Args:
        conversation_id: ID of the conversation
    """
    try:
        chat_message_crud.create_resource(
            {
                "conversation_id": conversation_id,
                "role": "system",
                "content": SYSTEM_MESSAGE,
                "sequence_order": 1,
            }
        )
    except Exception as e:
        logger.error(f"Error creating system message: {e}", exc_info=True)
        raise


def process_agent_response(response: str, sources: List[str]) -> str:
    """
    Process agent response by cleaning and adding proper source formatting.

    Args:
        response: Raw agent response
        sources: List of source URLs

    Returns:
        Processed response with proper citations
    """
    if not response:
        return "I apologize, but I couldn't generate a proper response. Please try rephrasing your question."

    # Clean any malformed citations
    response = re.sub(r"\[\[\[(\d+)\]\]\([^)]+\)\]\([^)]+\)", r"[[\1]]", response)

    # If we have sources, ensure proper citation format
    if sources:
        for i, url in enumerate(sources, 1):
            # Replace simple [1] with proper [[1]](url) format
            response = re.sub(rf"\[{i}\](?!\()", f"[[{i}]]({url})", response)

    return response


def validate_query(query: str) -> str:
    """
    Validate and clean user query.

    Args:
        query: Raw user query

    Returns:
        Cleaned and validated query
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty")

    # Remove excessive whitespace
    query = " ".join(query.split())

    # Limit query length
    if len(query) > 1000:
        query = query[:1000] + "..."

    return query


# --- ROUTES ---


@router.post(
    "/conversation",
    response_model=ConversationCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
    description="Creates a new conversation with a system message",
)
def create_conversation():
    """
    Create a new conversation.

    Returns:
        ConversationCreateResponse with the new conversation ID
    """
    try:
        conv = conversation_session_crud.create_resource({"id": str(uuid.uuid4())})
        create_system_message(conv["id"])
        return ConversationCreateResponse(conversation_id=conv["id"])
    except Exception as e:
        logger.error(f"Error creating conversation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create conversation",
        )


@router.get(
    "/conversation/{conversation_id}",
    response_model=ConversationResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get conversation history",
    description="Retrieve all messages in a conversation",
)
def get_conversation(conversation_id: str):
    """
    Get conversation history.

    Args:
        conversation_id: ID of the conversation to retrieve

    Returns:
        ConversationResponse with conversation details and messages

    Raises:
        HTTPException: If conversation not found
    """
    try:
        conv = conversation_session_crud.get_resource(
            resource_id=None, where=[Conversation.id == conversation_id]
        )
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
            )

        messages = chat_message_crud.list_resource(
            where=[Message.conversation_id == conversation_id],
            order_by=["sequence_order"],
        )

        # Convert database messages to schema format
        message_list = []
        for msg in messages:
            message_list.append(
                {
                    "role": msg.get("role", ""),
                    "content": msg.get("content", ""),
                    "tool_call_id": None,
                    "sequence_order": msg.get("sequence_order"),
                    "created_at": msg.get("created_at"),
                }
            )

        return ConversationResponse(
            conversation_id=conversation_id, messages=message_list
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting conversation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conversation",
        )


@router.post(
    "/message",
    response_model=MessageResponse,
    summary="Send a message",
    description="Send a message to the assistant and get a response",
)
def send_message(request: MessageRequest):
    """
    Send a message and get a response using the LangChain agent.

    Args:
        request: MessageRequest containing the message and optional conversation_id

    Returns:
        MessageResponse with the assistant's response or error message
    """
    try:
        # Validate and clean user query
        user_message = validate_query(request.message)

        conv_id = request.conversation_id

        # Create new conversation if none provided or doesn't exist
        if not conv_id or not conversation_session_crud.get_resource(
            resource_id=None, where=[Conversation.id == conv_id]
        ):
            conv = conversation_session_crud.create_resource({"id": str(uuid.uuid4())})
            conv_id = conv["id"]
            create_system_message(conv_id)

        # Save user message
        next_seq = get_next_sequence_order(conv_id)
        chat_message_crud.create_resource(
            {
                "conversation_id": conv_id,
                "role": "user",
                "content": user_message,
                "sequence_order": next_seq,
            }
        )

        # Get conversation history
        chat_history = get_conversation_history(conv_id)

        # Use agent to process the message
        agent_response = agent_executor.invoke(
            {"input": user_message, "chat_history": chat_history}
        )

        # Extract response and sources
        response_content = agent_response.get("output", "")

        # Extract sources from intermediate steps if any
        sources = []
        tool_outputs = []

        if "intermediate_steps" in agent_response:
            for step in agent_response["intermediate_steps"]:
                if len(step) > 1 and isinstance(step[1], dict):
                    tool_output = step[1]
                    tool_outputs.append(tool_output)
                    if "sources" in tool_output and tool_output["sources"]:
                        sources.extend(tool_output["sources"])

        # Remove duplicates from sources
        unique_sources = list(dict.fromkeys(sources))

        # Process response
        processed_response = process_agent_response(response_content, unique_sources)

        # Add sources section if we have sources
        if unique_sources:
            sources_markdown, _ = format_sources_from_tool_result(tool_outputs)
            if sources_markdown and "## Sources" not in processed_response:
                processed_response += sources_markdown

        # Save assistant response
        next_seq = get_next_sequence_order(conv_id)
        chat_message_crud.create_resource(
            {
                "conversation_id": conv_id,
                "role": "assistant",
                "content": processed_response,
                "sequence_order": next_seq,
            }
        )

        return MessageResponse(
            conversation_id=conv_id,
            response=processed_response,
            tool_used="hybrid_gitlab_search" if unique_sources else None,
            tool_result=tool_outputs[0].get("content", "") if tool_outputs else None,
            sources=unique_sources if unique_sources else None,
            error=None,  # No error
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return MessageResponse(
            conversation_id="",
            response="",
            tool_used=None,
            tool_result=None,
            sources=None,
            error=f"Validation error: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error sending message: {e}", exc_info=True)
        return MessageResponse(
            conversation_id="",
            response="",
            tool_used=None,
            tool_result=None,
            sources=None,
            error="Failed to process message. Please try again later.",
        )


@router.post(
    "/message/stream",
    summary="Send a message with streaming response",
    description="Send a message and get a streaming response using the agent",
)
async def send_message_stream(request: MessageRequest):
    """
    Send a message and get a streaming response using the LangChain agent.

    Args:
        request: MessageRequest containing the message and optional conversation_id

    Returns:
        StreamingResponse with the assistant's response
    """
    try:
        # Validate and clean user query
        user_message = validate_query(request.message)

        conv_id = request.conversation_id

        # Create new conversation if none provided or doesn't exist
        if not conv_id or not conversation_session_crud.get_resource(
            resource_id=None, where=[Conversation.id == conv_id]
        ):
            conv = conversation_session_crud.create_resource({"id": str(uuid.uuid4())})
            conv_id = conv["id"]
            create_system_message(conv_id)

        # Save user message
        next_seq = get_next_sequence_order(conv_id)
        chat_message_crud.create_resource(
            {
                "conversation_id": conv_id,
                "role": "user",
                "content": user_message,
                "sequence_order": next_seq,
            }
        )

        # Get conversation history
        chat_history = get_conversation_history(conv_id)

        async def streamer():
            # Initial info message
            yield f"data: {json.dumps({'type': 'info', 'content': 'Processing your request...', 'conversation_id': conv_id})}\n\n"

            try:
                full_response = ""
                sources = []
                tool_outputs = []

                # Stream agent response
                async for chunk in agent_executor.astream(
                    {"input": user_message, "chat_history": chat_history}
                ):
                    # Handle agent output
                    if "output" in chunk:
                        content = chunk["output"]
                        full_response += content
                        yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"

                    # Handle intermediate steps (tool calls)
                    if "intermediate_steps" in chunk:
                        for step in chunk["intermediate_steps"]:
                            if len(step) > 1 and isinstance(step[1], dict):
                                tool_output = step[1]
                                tool_outputs.append(tool_output)
                                if "sources" in tool_output and tool_output["sources"]:
                                    sources.extend(tool_output["sources"])

                # Remove duplicates from sources
                unique_sources = list(dict.fromkeys(sources))

                # Process final response
                processed_response = process_agent_response(
                    full_response, unique_sources
                )

                # Add sources section if we have sources
                if unique_sources:
                    sources_markdown, _ = format_sources_from_tool_result(tool_outputs)
                    if sources_markdown and "## Sources" not in processed_response:
                        processed_response += sources_markdown
                        yield f"data: {json.dumps({'type': 'sources', 'content': sources_markdown})}\n\n"

                # Save assistant response
                next_seq = get_next_sequence_order(conv_id)
                chat_message_crud.create_resource(
                    {
                        "conversation_id": conv_id,
                        "role": "assistant",
                        "content": processed_response,
                        "sequence_order": next_seq,
                    }
                )

                yield f"data: {json.dumps({'type': 'done', 'conversation_id': conv_id, 'sources': unique_sources})}\n\n"

            except Exception as e:
                logger.error(f"Streaming error: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'content': f'Error processing request: {str(e)}'})}\n\n"
                yield f"data: {json.dumps({'type': 'done', 'error': True})}\n\n"

        return StreamingResponse(
            streamer(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error in streaming endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process streaming request",
        )
