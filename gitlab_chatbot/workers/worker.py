from functools import cache
import os
import json
import time
import requests
from urllib.parse import quote
from typing import Dict, List, Set, Tuple
from celery import Celery
from celery.schedules import crontab
import concurrent.futures

from gitlab_chatbot.db.crud_helper import (
    document_crud,
    checkpoint_crud,
    commit_tracker_crud,
)

from gitlab_chatbot.models.document_db import Document, Checkpoint, CommitTracker
from gitlab_chatbot.settings import config

if not os.path.exists(config.gitlab_conf):
    raise FileNotFoundError(
        f"Tracked repositories configuration file not found: {config.gitlab_conf}"
    )
TRACKED_REPOS = json.load(open(config.gitlab_conf))

GITLAB_API = "https://gitlab.com/api/v4"
HEADERS = {"PRIVATE-TOKEN": config.gitlab_token} if config.gitlab_token else {}
MAX_RETRIES = 5
GITLAB_RATE_LIMIT = 429
CHUNK_SIZE = 1000  # Approximate character limit for document chunks
MAX_WORKERS = 6

# --- Celery Setup ---
app = Celery(
    "gitlab_scraper",
    broker=config.celery_broker_url,
)
app.conf.beat_schedule = {
    "scrape-gitlab-every-6-hours": {
        "task": "gitlab_chatbot.worker.worker.scrape_gitlab",
        "schedule": crontab(hour="*/6"),
    },
}
app.conf.update(timezone="UTC")


def safe_get(url: str, params: Dict | None = None) -> requests.Response:
    backoff = 2
    for attempt in range(MAX_RETRIES):
        print(f"\U0001F310 GET {url} (Attempt {attempt + 1})")
        resp = requests.get(url, headers=HEADERS, params=params)
        if resp.status_code == GITLAB_RATE_LIMIT or resp.status_code >= 500:
            wait_time = backoff**attempt
            print(f"⚠️ HTTP {resp.status_code}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
            continue
        resp.raise_for_status()
        return resp
    raise Exception(f"❌ Failed GET after {MAX_RETRIES} attempts: {url}")


@cache
def get_project_id(project_path: str) -> int:
    url = f"{GITLAB_API}/projects/{quote(project_path, safe='')}"
    return safe_get(url).json()["id"]


def get_commits(project_id: int, path: str, since: str | None = None) -> List[Dict]:
    url = f"{GITLAB_API}/projects/{project_id}/repository/commits"
    params = {"path": path, "per_page": 100}
    if since:
        params["since"] = since
    return safe_get(url, params).json()


def get_commit_diff(project_id: int, commit_sha: str) -> List[Dict]:
    url = f"{GITLAB_API}/projects/{project_id}/repository/commits/{commit_sha}/diff"
    return safe_get(url).json()


def get_tree_entries(
    project_id: int, path: str = "", extensions: List[str] | None = None
) -> List[Dict]:
    all_entries = []
    page = 1
    while True:
        url = f"{GITLAB_API}/projects/{project_id}/repository/tree"
        params = {"path": path, "per_page": 100, "page": page, "recursive": True}
        try:
            resp = safe_get(url, params)
            entries = resp.json()
            if not entries:
                break
            filtered_entries = [
                entry
                for entry in entries
                if entry["type"] == "blob"
                and (
                    not extensions
                    or any(entry["path"].endswith(ext) for ext in extensions)
                )
            ]
            all_entries.extend(filtered_entries)
            page += 1
            if "X-Next-Page" not in resp.headers or resp.headers["X-Next-Page"] == "":
                break
        except Exception as e:
            print(f"❌ Error fetching tree entries for {path}: {e}")
            break
    return all_entries


def get_file_content(project_id: int, file_path: str, commit_sha: str) -> str:
    url = f"{GITLAB_API}/projects/{project_id}/repository/files/{quote(file_path, safe='')}/raw"
    params = {"ref": commit_sha}
    resp = safe_get(url, params)
    return resp.text


def chunk_content(content: str, source: str, collection_id: str) -> List[Dict]:
    chunks = []
    for i, start in enumerate(range(0, len(content), CHUNK_SIZE)):
        chunk_text = content[start : start + CHUNK_SIZE]
        chunks.append(
            {
                "collection_id": collection_id,
                "source": source,
                "chunk_index": i,
                "content": chunk_text,
                "document_metadata": {"length": len(chunk_text)},
            }
        )
    return chunks


def process_file_content(
    project_id: int,
    file_path: str,
    commit_sha: str,
    collection_id: str,
) -> None:
    try:
        existing_checkpoint = checkpoint_crud.get_resource(
            resource_id=None,
            where=[
                Checkpoint.commit_id == commit_sha,
                Checkpoint.file_path == file_path,
            ],
        )

        if existing_checkpoint and existing_checkpoint["state"] in [
            "INSERTED",
            "EMBEDDED",
        ]:
            print(f"⏭️ Skipping {file_path}: already processed for commit {commit_sha}")
            return

        content = get_file_content(project_id, file_path, commit_sha)
        chunks = chunk_content(content, file_path, collection_id)

        if not existing_checkpoint:
            document_crud.delete_resource(
                resource_id=None,
                where=[
                    Document.source == file_path,
                    Document.collection_id == collection_id,
                ],
            )

            for chunk in chunks:
                document_crud.create_resource(chunk)

        checkpoint_data = {
            "commit_id": commit_sha,
            "file_path": file_path,
            "state": "INSERTED",
        }
        if existing_checkpoint:
            checkpoint_crud.update_resource(
                data=checkpoint_data,
                where=[
                    Checkpoint.commit_id == commit_sha,
                    Checkpoint.file_path == file_path,
                ],
            )
        else:
            checkpoint_crud.create_resource(checkpoint_data)

        for chunk in chunks:
            app.send_task(
                "gitlab_chatbot.tasks.embed",
                args=[chunk["source"], chunk["chunk_index"], collection_id],
                queue="embedding",
            )
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        checkpoint_crud.create_resource(
            {
                "commit_id": commit_sha,
                "file_path": file_path,
                "state": "ERROR",
                "error_message": str(e),
            }
        )


def get_file_changes(
    project_id: int,
    repo_config: Dict,
    last_commit: str | None,
    last_commit_time: str | None,
) -> Tuple[Set[str], Set[str], Set[str]]:
    new_files = set()
    updated_files = set()
    deleted_files = set()

    current_files = set(
        entry["path"]
        for entry in get_tree_entries(
            project_id, repo_config["subdir"], repo_config["extensions"]
        )
    )

    checkpoints = checkpoint_crud.list_resource(where=[Checkpoint.state != "DELETED"])
    checkpoint_files = {cp["file_path"] for cp in checkpoints}

    if not last_commit:
        new_files = current_files
        return new_files, updated_files, deleted_files

    commits = get_commits(project_id, repo_config["api_path"], since=last_commit_time)
    new_commits = []
    for commit in commits:
        if commit["id"] == last_commit:
            break
        new_commits.append(commit)
    new_commits.reverse()

    for commit in new_commits:
        for diff in get_commit_diff(project_id, commit["id"]):
            file_path = diff.get("new_path", diff.get("old_path"))
            if not file_path:
                continue
            if not file_path.startswith(repo_config["subdir"]) or not any(
                file_path.endswith(ext) for ext in repo_config["extensions"]
            ):
                continue
            if diff.get("deleted_file"):
                deleted_files.add(file_path)
            elif diff.get("new_path") and not diff.get("new_file"):
                updated_files.add(file_path)
            elif diff.get("new_file"):
                new_files.add(file_path)

    deleted_files.update(checkpoint_files - current_files)

    return new_files, updated_files, deleted_files


@app.task
def scrape_gitlab():
    session = document_crud.get_sync_session()
    try:
        for label, repo_config in TRACKED_REPOS.items():
            print(f"\n🔍 Processing {label.upper()}")
            project_id = get_project_id(repo_config["path"])

            tracker = commit_tracker_crud.get_resource(
                resource_id=None, where=[CommitTracker.project_id == str(project_id)]
            )
            last_commit = tracker["last_commit_id"] if tracker else None
            last_commit_time = (
                tracker["last_commit_time"].isoformat() if tracker else None
            )

            if not last_commit or not last_commit_time:
                print(f"🔄 Initial run for {label}. Processing all files.")
                last_commit = None
                last_commit_time = None
            else:
                print(
                    f"🔄 Last processed commit for {label}: {last_commit} at {last_commit_time}"
                )

            new_files, updated_files, deleted_files = get_file_changes(
                project_id, repo_config, last_commit, last_commit_time
            )

            latest_commit = get_commits(project_id, repo_config["api_path"])[0]
            commit_sha = latest_commit["id"]

            def process_path(file_path):
                print(
                    f"📄 Processing {'new' if file_path in new_files else 'updated'} file: {file_path}"
                )
                process_file_content(
                    project_id,
                    file_path,
                    commit_sha,
                    repo_config["collection_id"],
                )

            all_to_process = list(new_files | updated_files)
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                list(executor.map(process_path, all_to_process))

            for file_path in deleted_files:
                print(f"🗑️ Marking deleted file: {file_path}")
                checkpoint_crud.update_resource(
                    data={"state": "DELETED"},
                    where=[
                        Checkpoint.file_path == file_path,
                        Checkpoint.state != "DELETED",
                    ],
                )
                document_crud.delete_resource(
                    where=[
                        Document.source == file_path,
                        Document.collection_id == repo_config["collection_id"],
                    ]
                )

            tracker_data = {
                "project_id": str(project_id),
                "last_commit_id": commit_sha,
                "last_commit_time": latest_commit["created_at"],
            }
            if tracker:
                commit_tracker_crud.update_resource(
                    data=tracker_data,
                    where=[CommitTracker.project_id == str(project_id)],
                )
            else:
                commit_tracker_crud.create_resource(tracker_data)

            print(
                f"✅ Processed {label}: {len(new_files)} new, {len(updated_files)} updated, {len(deleted_files)} deleted"
            )

    except Exception as e:
        print(f"❌ Error in scrape_gitlab: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    scrape_gitlab()
