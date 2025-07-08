#!/bin/bash
set -e

case "$SERVICE_TYPE" in
api)
  exec poetry run uvicorn gitlab_chatbot.__main__:app --host 0.0.0.0 --port 8000 $EXTRA_ARGS
  ;;
celery-worker)
  exec poetry run celery -A gitlab_chatbot.workers.files_processor worker --loglevel=info --pool threads --concurrency=${WORKER_CONCURRENCY:-12} -Q ${WORKER_QUEUE:-processor}
  ;;
celery-embed)
  exec poetry run celery -A gitlab_chatbot.workers.embed worker --loglevel=info --pool gevent --concurrency=${WORKER_CONCURRENCY:-48} -Q ${WORKER_QUEUE:-embedding} $EXTRA_ARGS
  ;;
celery-beat)
  exec poetry run celery -A gitlab_chatbot.workers.files_fetcher worker --beat -Q celery --loglevel=info --pool gevent
  ;;
*)
  echo "Unknown SERVICE_TYPE: $SERVICE_TYPE"
  exit 1
  ;;
esac
