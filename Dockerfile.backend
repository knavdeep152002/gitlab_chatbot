FROM python:3.11-slim

RUN apt-get update && apt-get install -y build-essential libpq-dev curl && rm -rf /var/lib/apt/lists/*

RUN pip3 install poetry
WORKDIR /app

COPY . .
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-ansi --only main

EXPOSE 8000
COPY scripts/entrypoint.sh /bin/entrypoint.sh
RUN chmod +x /bin/entrypoint.sh

ENTRYPOINT [ "/bin/entrypoint.sh" ]