import streamlit as st
import requests
from datetime import datetime
from config import API_BASE_URL, STREAMLIT_CONFIG, EXAMPLE_QUESTIONS #type: ignore

def init_session_state():
    """Initialize session state variables"""
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "is_loading" not in st.session_state:
        st.session_state.is_loading = False

def create_new_conversation():
    """Create a new conversation"""
    try:
        response = requests.post(f"{API_BASE_URL}/conversation")
        if response.status_code == 201:
            data = response.json()
            st.session_state.conversation_id = data["conversation_id"]
            st.session_state.messages = []
            return True
        else:
            st.error(f"Failed to create conversation: {response.status_code}")
            return False
    except Exception as e:
        st.error(f"Error creating conversation: {str(e)}")
        return False

def send_message(message):
    """Send a message to the chatbot API"""
    if not st.session_state.conversation_id:
        if not create_new_conversation():
            return None
    
    try:
        payload = {
            "conversation_id": st.session_state.conversation_id,
            "message": message
        }
        
        response = requests.post(
            f"{API_BASE_URL}/message",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        st.error(f"Error sending message: {str(e)}")
        return None

def display_message(role, content, sources=None):
    """Display a message in the chat interface"""
    if role == "user":
        with st.chat_message("user"):
            st.write(content)
    elif role == "assistant":
        with st.chat_message("assistant"):
            st.markdown(content)
            
            # Display sources if available
            if sources:
                with st.expander("📚 Sources"):
                    for i, source in enumerate(sources, 1):
                        st.markdown(f"{i}. [{source}]({source})")

def main():
    st.set_page_config(
        page_title=STREAMLIT_CONFIG["page_title"],
        page_icon=STREAMLIT_CONFIG["page_icon"],
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    init_session_state()
    
    # Sidebar
    with st.sidebar:
        st.title("🤖 GitLab Handbook Chat")
        st.markdown("---")
        
        # New conversation button
        if st.button("🆕 New Conversation", use_container_width=True):
            if create_new_conversation():
                st.success("New conversation created!")
                st.rerun()
        
        st.markdown("---")
        
        # Conversation info
        if st.session_state.conversation_id:
            st.info(f"**Conversation ID:**\n`{st.session_state.conversation_id}`")
        
        st.markdown("---")
        
        # About section
        st.markdown("### About")
        st.markdown("""
        This chatbot helps you find information from the GitLab Handbook and documentation.
        
        **Features:**
        - 🔍 Semantic search across GitLab docs
        - 📚 Source citations
        - 💬 Conversation history
        - 🚀 Real-time responses
        """)
        
        st.markdown("---")
        
        # Example questions
        st.markdown("### Example Questions")
        
        for question in EXAMPLE_QUESTIONS:
            if st.button(question, key=f"example_{question}"):
                st.session_state.example_question = question
                st.rerun()

    # Main chat interface
    st.title("💬 GitLab Handbook Chat")
    st.markdown("Ask questions about GitLab's handbook, policies, and documentation.")
    
    # Display conversation history
    for message in st.session_state.messages:
        display_message(
            message["role"], 
            message["content"], 
            message.get("sources")
        )
    
    # Handle example question from sidebar
    if "example_question" in st.session_state:
        user_input = st.session_state.example_question
        del st.session_state.example_question
        
        # Add user message to history
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now()
        })
        
        # Display user message
        display_message("user", user_input)
        
        # Send to API and get response
        with st.spinner("🤔 Thinking..."):
            response = send_message(user_input)
        
        if response:
            # Add assistant response to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": response["response"],
                "sources": response.get("sources"),
                "timestamp": datetime.now()
            })
            
            # Display assistant response
            display_message("assistant", response["response"], response.get("sources"))
        else:
            st.error("Failed to get response from the chatbot.")
    
    # Chat input
    if prompt := st.chat_input("Ask a question about GitLab..."):
        # Add user message to history
        st.session_state.messages.append({
            "role": "user",
            "content": prompt,
            "timestamp": datetime.now()
        })
        
        # Display user message
        display_message("user", prompt)
        
        # Send to API and get response
        with st.spinner("🤔 Thinking..."):
            response = send_message(prompt)
        
        if response:
            # Add assistant response to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": response["response"],
                "sources": response.get("sources"),
                "timestamp": datetime.now()
            })
            
            # Display assistant response
            display_message("assistant", response["response"], response.get("sources"))
        else:
            st.error("Failed to get response from the chatbot.")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; font-size: 0.8em;'>
            Powered by GitLab Handbook Search • Built with Streamlit
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main() 
