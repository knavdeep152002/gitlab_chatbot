# GitLab Handbook Chatbot

A production-ready, end-to-end chatbot system for querying the GitLab Handbook and Direction pages using advanced RAG (Retrieval-Augmented Generation) and Langchain Agent techniques. The system features robust ingestion and periodic syncing of documentation, and a conversational chatbot interface with source citations.

---

## 🚀 Features

- **Automated Ingestion & Sync**: Periodically fetches and embeds GitLab Handbook and Direction pages every 3 hours using a worker-based approach (Celery + RabbitMQ).
- **Conversational Chatbot**: Uses Langchain Agent and RAG to answer questions with context and sources from the ingested database.
- **Modern UI**: Streamlit-based chat interface with example questions, conversation history, and clickable citations.
- **Scalable Architecture**: Modular backend (FastAPI), distributed workers, and containerized deployment.

---

## 🛠️ Architecture Overview

### 1. **Ingestion & Sync Process**
- **Celery Workers**: Periodically fetch and process documentation from GitLab Handbook and Direction pages.
- **Embedding Workers**: Generate vector embeddings for new/updated documents.
- **Scheduler (Celery Beat)**: Triggers sync jobs every 3 hours.
- **Database**: Stores all documents and embeddings for fast retrieval.

### 2. **Chatbot Process**
- **API (FastAPI)**: Exposes endpoints for chat, conversation management, and search.
- **Langchain Agent + RAG**: Answers user queries using hybrid search and context retrieval from the database.
- **Streamlit UI**: User-friendly chat interface.

---

## ⚡ Quick Start

### Prerequisites
- Python 3.10+
- [Poetry](https://python-poetry.org/)
- Docker & Docker Compose
- [Just](https://github.com/casey/just) (for local command automation)

---

## 🖥️ Local Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-org/gitlab-handbook-chatbot.git
   cd gitlab-handbook-chatbot
   ```

2. **Install dependencies:**
   ```bash
   poetry install
   ```

3. **Set up environment variables:**
   - Copy `.env.example` to `.env` and fill in required values (API keys, DB URL, etc.)

4. **Database setup:**
   - Start Postgres (locally or via Docker)
   - Run migrations:
     ```bash
     just migrate
     ```

5. **Run the backend API:**
   ```bash
   just api
   # or
   poetry run uvicorn gitlab_chatbot.__main__:app --host 0.0.0.0 --port 8000
   ```

6. **Start Celery workers and beat:**
   ```bash
   just celery-worker
   just celery-embed
   just celery-beat
   ```

7. **Run the Streamlit app:**
   ```bash
   cd streamlit
   pip install -r requirements.txt
   streamlit run streamlit_app.py
   ```
   - The app will be available at [http://localhost:8502](http://localhost:8502)

---

## 🐳 Docker Compose Deployment

1. **Build and start all services:**
   ```bash
   docker-compose up --build --scale celery-worker=2 --scale celery-embed=3
   ```
   - This will start:
     - Postgres (with vector support)
     - RabbitMQ (for Celery)
     - API (FastAPI)
     - Celery workers (for ingestion)
     - Celery embed workers (for embeddings)
     - Celery beat (for periodic sync)
     - Streamlit UI

2. **Access the services:**
   - **API:** [http://localhost:8000](http://localhost:8000)
   - **Streamlit UI:** [http://localhost:8501](http://localhost:8501)
   - **RabbitMQ UI:** [http://localhost:15672](http://localhost:15672) (user: guest, pass: guest)

---

## ⚙️ Configuration & Environment Variables

- `db_url`: Postgres connection string (e.g., `postgresql://postgres:postgres@postgres:5432/gitlab`)
- `broker_url`: RabbitMQ connection string (e.g., `amqp://guest:guest@rabbitmq:5672/`)
- `GEMINI_API_KEY`: Your Gemini API key for LLM access
- `GITLAB_CHAT_API_URL`: (Streamlit) URL of the backend API

Set these in your `.env` file or as environment variables in Docker Compose.

---

## 🕒 Periodic Ingestion & Sync
- The system automatically syncs with the latest GitLab Handbook and Direction pages every 3 hours using Celery Beat and workers.
- No manual intervention is needed for regular updates.

---

## 💬 Chatbot Usage
- Ask questions about GitLab’s handbook, policies, and documentation.
- Get real-time answers with source citations.
- Use the Streamlit UI for a modern chat experience.

---

## 🧑‍💻 Development & Customization
- Add new ingestion sources by extending the worker logic.
- Customize the chat UI in `streamlit/streamlit_app.py`.
- Extend API endpoints in the FastAPI backend.

---

## 🛟 Troubleshooting
- **API not responding?** Ensure all containers are running and ports are not blocked.
- **Streamlit UI not working?** Check the `GITLAB_CHAT_API_URL` and browser console for errors.
- **Worker errors?** Check logs with `docker-compose logs celery-worker`
- **Database issues?** Ensure Postgres is running and accessible.
