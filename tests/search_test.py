import pytest
from gitlab_chatbot.utils.hybrid_search import generate_rag_context
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from gitlab_chatbot.settings import config

TEST_DATABASE_URL = config.db_url

_test_engine = create_engine(TEST_DATABASE_URL, echo=False, future=True)
_TestSessionLocal = sessionmaker(bind=_test_engine, class_=Session, expire_on_commit=False)


def get_test_session() -> Session:
    """
    Creates a SQLAlchemy session for use in tests.
    Assumes a separate test DB is configured via `config.test_db_url`.
    """
    return _TestSessionLocal()

@pytest.fixture(scope="module")
def db_session():
    session = get_test_session()
    yield session
    session.close()

def test_hybrid_search_basic(db_session):
    query = "DevOps platform"
    results = generate_rag_context(
        session=db_session,
        query=query,
    )
    assert isinstance(results, tuple)
    assert len(results) == 2
    context, sources = results
    assert isinstance(context, str)
    assert isinstance(sources, set)
    assert len(sources) > 0
    assert all(isinstance(source, str) for source in sources)
