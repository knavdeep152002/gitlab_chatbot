from pydantic import Field
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    db_url: str
    gitlab_conf: str = Field(default="config/gitlab.json")
    gitlab_token: str | None = Field(default=None)
    celery_broker_url: str = Field(default="pyamqp://guest@localhost//")

config = Config() # type: ignore
