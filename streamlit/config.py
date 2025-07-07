import os

# API Configuration
API_BASE_URL = os.getenv("GITLAB_CHAT_API_URL", "http://localhost:8000/api/v1/chatbot")

# Streamlit Configuration
STREAMLIT_CONFIG = {
    "page_title": "GitLab Handbook Chat",
    "page_icon": "🤖",
    "layout": "wide",
    "initial_sidebar_state": "expanded"
}

# Example Questions
EXAMPLE_QUESTIONS = [
    "What is GitLab's mission?",
    "What are GitLab's core values?",
    "How does GitLab handle security?",
    "What is GitLab's approach to remote work?",
    "How does GitLab CI/CD work?",
    "What are the consequences of not testing a Business Continuity Plan?",
    "What is GitLab's pricing strategy?",
    "How does GitLab handle diversity and inclusion?",
    "What are GitLab's development practices?",
    "How does GitLab manage customer support?"
] 