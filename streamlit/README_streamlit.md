# GitLab Handbook Chat - Streamlit Interface

A user-friendly Streamlit web application that provides a chat interface for the GitLab Handbook chatbot.

## Features

- 🤖 **Interactive Chat Interface**: Clean, modern chat UI built with Streamlit
- 🔍 **Semantic Search**: Powered by hybrid search across GitLab documentation
- 📚 **Source Citations**: Clickable links to original handbook pages
- 💬 **Conversation History**: Maintains context across multiple messages
- 🚀 **Real-time Responses**: Fast, responsive chat experience
- 📱 **Responsive Design**: Works on desktop and mobile devices

## Prerequisites

1. **GitLab Chatbot API**: Make sure your FastAPI backend is running on `http://localhost:8000`
2. **Python 3.8+**: Required for Streamlit
3. **Dependencies**: Install required packages

## Installation

1. **Install Streamlit dependencies**:
   ```bash
   pip install -r requirements_streamlit.txt
   ```

2. **Configure the API URL** (optional):
   - Edit `config.py` to change the API base URL
   - Or set environment variable: `export GITLAB_CHAT_API_URL=http://your-api-url:8000/api/v1/chatbot`

## Running the App

1. **Start the Streamlit app**:
   ```bash
   streamlit run streamlit_app.py
   ```

2. **Open your browser**:
   - Navigate to `http://localhost:8501`
   - The app will automatically open in your default browser

## Usage

### Basic Chat
1. Type your question in the chat input at the bottom
2. Press Enter or click the send button
3. View the response with source citations

### Example Questions
Use the sidebar to try pre-configured example questions:
- What is GitLab's mission?
- What are GitLab's core values?
- How does GitLab handle security?
- What is GitLab's approach to remote work?
- How does GitLab CI/CD work?

### New Conversations
- Click "🆕 New Conversation" in the sidebar to start fresh
- Each conversation maintains its own history

### Source Citations
- Click the "📚 Sources" expander to see original handbook links
- All citations are clickable and lead to the source documentation

## Configuration

### Environment Variables
- `GITLAB_CHAT_API_URL`: API endpoint URL (default: `http://localhost:8000/api/v1/chatbot`)

### Customization
Edit `config.py` to modify:
- API base URL
- Page title and icon
- Example questions
- Streamlit configuration

## Troubleshooting

### API Connection Issues
- Ensure your FastAPI backend is running on the correct port
- Check the API URL in `config.py`
- Verify network connectivity

### Streamlit Issues
- Update Streamlit: `pip install --upgrade streamlit`
- Clear browser cache
- Check console for error messages

### Performance
- Large responses may take a few seconds
- The app caches conversation history in session state
- Consider increasing Streamlit's memory limits for large conversations

## Development

### Adding Features
1. **New UI Components**: Add to the main chat interface
2. **API Integration**: Extend the `send_message()` function
3. **Styling**: Modify the Streamlit components and CSS

### Testing
- Test with various question types
- Verify source citations work correctly
- Check responsive design on different screen sizes

## Architecture

```
streamlit_app.py          # Main Streamlit application
├── config.py             # Configuration settings
├── requirements_streamlit.txt  # Python dependencies
└── README_streamlit.md   # This documentation
```

## API Integration

The app integrates with your GitLab chatbot API endpoints:
- `POST /api/v1/chatbot/conversation` - Create new conversation
- `POST /api/v1/chatbot/message` - Send message and get response

## License

This Streamlit interface is part of the GitLab Handbook Chat project. 