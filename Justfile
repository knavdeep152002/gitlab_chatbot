set dotenv-load

default_port := '8000'

default:
  @just --list

# Build image for the application
build tag:
    docker build --secret id=git-pat,src=$HOME/.git_pat -t $IMAGE_REG/$IMAGE_REPO:$(git rev-parse HEAD) .
    docker tag $IMAGE_REG/$IMAGE_REPO:$(git rev-parse HEAD) $AR_IMAGE_REG/$IMAGE_REPO:{{tag}}

# push image to the container registry
push tag:
    docker push $AR_IMAGE_REG/$IMAGE_REPO:{{tag}}


# Download the release for the service from github
download tag:
    gh release -R $GIT_REPOSITORY download {{tag}} --skip-existing


# Install dependencies and the packages in a new python shell
install:
    poetry update && poetry install

run port=default_port:
    poetry run uvicorn gitlab_chatbot.__main__:app --log-level=debug --reload --port {{port}} --host 0.0.0.0

# Run organization metadata db migration
migrate:
    cd gitlab_chatbot && poetry run alembic upgrade head

downgrade:
    cd gitlab_chatbot && poetry run alembic downgrade -1

revision message:
    cd gitlab_chatbot && poetry run alembic revision --autogenerate -m "{{message}}"

shell:
    $SHELL

celery-worker:
    poetry run celery -A gitlab_chatbot.workers.files_processor worker --loglevel=info --pool threads --concurrency=12

celery-embed:
    poetry run celery -A gitlab_chatbot.workers.embed worker --loglevel=info --pool gevent --concurrency=48 -Q embedding

celery-beat:
    poetry run celery -A gitlab_chatbot.workers.files_fetcher beat --loglevel=info
