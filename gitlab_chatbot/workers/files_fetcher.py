import json
import logging
from datetime import datetime
from celery import Celery
from celery.schedules import crontab
from typing import Set, Tuple

from gitlab_chatbot.settings import config
from gitlab_chatbot.models.document_db import CommitTracker, Checkpoint, Document
from gitlab_chatbot.db.crud_helper import checkpoint_crud, commit_tracker_crud
from gitlab_chatbot.workers.files_processor import document_crud, process_file
from gitlab_chatbot.workers.gitlab_utils import (
    get_project_id,
    get_commits,
    get_commit_diff,
    get_tree_entries,
)
from gitlab_chatbot.workers.schema import CheckpointState

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Celery Setup ---
app = Celery("files_fetcher", broker=config.celery_broker_url)
app.conf.beat_schedule = {
    "fetch-gitlab-files-every-6-hours": {
        "task": "scraper.files_fetcher.fetch_files",
        "schedule": crontab(hour="*/6"),
    }
}
app.conf.update(timezone="UTC")

TRACKED_REPOS = json.load(open(config.gitlab_conf))


def determine_file_changes(
    project_id: int, repo_config: dict, last_commit: str | None, last_time: str | None
) -> Tuple[Set[str], Set[str], str]:
    current_files = {
        entry["path"]
        for entry in get_tree_entries(
            project_id, repo_config["subdir"], repo_config["extensions"]
        )
    }
    checkpoints = checkpoint_crud.list_resource(where=[Checkpoint.state != "DELETED"])
    seen_files = {cp["file_path"] for cp in checkpoints}

    changed_files = set()
    deleted_files = set()
    if not last_commit:
        changed_files = current_files
    else:
        commits = get_commits(project_id, repo_config["api_path"], since=last_time)
        for commit in commits:
            if commit["id"] == last_commit:
                break
            for diff in get_commit_diff(project_id, commit["id"]):
                path = diff.get("new_path") or diff.get("old_path")
                if (
                    not path
                    or not path.startswith(repo_config["subdir"])
                    or not any(path.endswith(ext) for ext in repo_config["extensions"])
                ):
                    continue

                if diff.get("deleted_file"):
                    deleted_files.add(path)
                else:
                    changed_files.add(path)

    new_or_failed = current_files - seen_files
    # deleted_files.update(seen_files - current_files)
    return (
        new_or_failed.union(changed_files),
        deleted_files,
        get_commits(project_id, repo_config["api_path"])[0]["id"],
    )


@app.task(
    name="scraper.files_fetcher.fetch_files",
    opts={"acks_late": True, "max_retries": 3, "retry_backoff": True},
)
def fetch_files():
    logger.info("\U0001f50d Starting file fetch beat task...")
    for label, repo_config in TRACKED_REPOS.items():
        try:
            logger.info(f"\n\U0001f4cb Repo: {label.upper()}")
            project_id = get_project_id(repo_config["path"])

            tracker = commit_tracker_crud.get_resource(
                resource_id=None, where=[CommitTracker.project_id == str(project_id)]
            )
            last_commit = tracker["last_commit_id"] if tracker else None
            last_time = tracker["last_commit_time"].isoformat() if tracker else None

            to_process, to_delete, latest_commit = determine_file_changes(
                project_id, repo_config, last_commit, last_time
            )

            for file_path in sorted(to_process):
                logger.info(f"Enqueuing file: {file_path}")
                existing_checkpoint = checkpoint_crud.get_resource(
                    resource_id=None,
                    where=[
                        Checkpoint.file_path == file_path,
                    ],
                )
                if existing_checkpoint:
                    checkpoint_crud.update_resource(
                        data={
                            "state": CheckpointState.PROCESS_PENDING,
                            "commit_id": latest_commit,
                        },
                        where=[Checkpoint.file_path == file_path],
                    )
                else:
                    checkpoint_crud.create_resource(
                        {
                            "commit_id": latest_commit,
                            "file_path": file_path,
                            "state": CheckpointState.PROCESS_PENDING,
                        }
                    )
                process_file.delay(
                    project_id=project_id,
                    file_path=file_path,
                    commit_sha=latest_commit,
                    collection_id=repo_config["collection_id"],
                )

            for file_path in sorted(to_delete):
                logger.info(f"Marking file for deletion: {file_path}")
                existing_checkpoint = checkpoint_crud.get_resource(
                    resource_id=None,
                    where=[
                        Checkpoint.file_path == file_path,
                    ],
                )
                if existing_checkpoint:
                    checkpoint_crud.update_resource(
                        data={"state": CheckpointState.DELETED},
                        where=[Checkpoint.file_path == file_path],
                    )
                else:
                    checkpoint_crud.create_resource(
                        {
                            "commit_id": latest_commit,
                            "file_path": file_path,
                            "state": CheckpointState.DELETED,
                        }
                    )
                # Delete from Document collection
                document_crud.delete_resource(
                    resource_id=None,
                    where=[
                        Document.source == file_path,
                        Document.collection_id == repo_config["collection_id"],
                    ],
                )

            commit_data = {
                "project_id": str(project_id),
                "last_commit_id": latest_commit,
                "last_commit_time": datetime.utcnow(),
            }
            if tracker:
                commit_tracker_crud.update_resource(
                    data=commit_data,
                    where=[CommitTracker.project_id == str(project_id)],
                )
            else:
                commit_tracker_crud.create_resource(commit_data)

        except Exception as e:
            logger.error(f"Failed fetching for repo {label}: {e}")
    logger.info("\u2705 File fetch cycle complete.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    fetch_files()  # For testing purposes, run immediately
    # In production, this will be scheduled by Celery Beat
