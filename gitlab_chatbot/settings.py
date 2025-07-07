from pydantic import Field
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    db_url: str
    gemini_api_key: str
    gemini_model: str = Field(default="gemini-2.0-flash") 
    huggingface_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    gitlab_conf: str = Field(default="config/gitlab.json")
    gitlab_token: str | None = Field(default=None)
    celery_broker_url: str = Field(default="pyamqp://guest@localhost//")

config = Config() # type: ignore
