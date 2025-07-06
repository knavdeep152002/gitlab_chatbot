from functools import cache
import time
import requests
import logging
from urllib.parse import quote
from typing import Dict, List
from gitlab_chatbot.settings import config

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

GITLAB_API = "https://gitlab.com/api/v4"
HEADERS = {"PRIVATE-TOKEN": config.gitlab_token} if config.gitlab_token else {}
MAX_RETRIES = 5
GITLAB_RATE_LIMIT = 429

def safe_get(url: str, params: Dict | None = None) -> requests.Response:
    backoff = 2
    for attempt in range(MAX_RETRIES):
        logger.info(f"GET {url} (Attempt {attempt + 1})")
        response = requests.get(url, headers=HEADERS, params=params)
        if response.status_code in [GITLAB_RATE_LIMIT] or response.status_code >= 500:
            wait = backoff**attempt
            logger.warning(f"HTTP {response.status_code}. Retrying in {wait}s...")
            time.sleep(wait)
            continue
        response.raise_for_status()
        return response
    raise Exception(f"Failed to GET after {MAX_RETRIES} retries: {url}")

@cache
def get_project_id(project_path: str) -> int:
    url = f"{GITLAB_API}/projects/{quote(project_path, safe='')}"
    project_id = safe_get(url).json()["id"]
    logger.info(f"Resolved project ID for {project_path}: {project_id}")
    return project_id

def get_commits(project_id: int, path: str, since: str | None = None) -> List[Dict]:
    url = f"{GITLAB_API}/projects/{project_id}/repository/commits"
    params = {"path": path, "per_page": 100}
    if since:
        params["since"] = since
    return safe_get(url, params).json()

def get_commit_diff(project_id: int, commit_sha: str) -> List[Dict]:
    url = f"{GITLAB_API}/projects/{project_id}/repository/commits/{commit_sha}/diff"
    return safe_get(url).json()

def get_tree_entries(project_id: int, path: str = "", extensions: List[str] | None = None) -> List[Dict]:
    all_entries = []
    page = 1
    while True:
        url = f"{GITLAB_API}/projects/{project_id}/repository/tree"
        params = {"path": path, "per_page": 100, "page": page, "recursive": True}
        resp = safe_get(url, params)
        entries = resp.json()
        if not entries:
            break
        filtered = [e for e in entries if e["type"] == "blob" and (not extensions or any(e["path"].endswith(ext) for ext in extensions))]
        all_entries.extend(filtered)
        page += 1
        if not resp.headers.get("X-Next-Page"):
            break
    logger.info(f"Fetched {len(all_entries)} file entries under path '{path}'")
    return all_entries

def get_file_content(project_id: int, file_path: str, commit_sha: str) -> str:
    url = f"{GITLAB_API}/projects/{project_id}/repository/files/{quote(file_path, safe='')}/raw"
    params = {"ref": commit_sha}
    content = safe_get(url, params).text
    logger.info(f"Fetched content for {file_path} at commit {commit_sha}")
    return content
