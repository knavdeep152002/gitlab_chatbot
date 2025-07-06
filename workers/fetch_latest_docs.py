import os
import json
import time
import requests
import concurrent.futures
from urllib.parse import quote

# --- Config ---
TRACKED_REPOS = {
    "handbook": {
        "path": "gitlab-com/content-sites/handbook",
        "api_path": "content/handbook",
        "subdir": "content/handbook",
        "extensions": [".md"],
    },
    "direction": {
        "path": "gitlab-com/www-gitlab-com",
        "api_path": "source/direction/",
        "subdir": "source/direction/",
        "extensions": [".md", ".md.erb"],
    },
}

GITLAB_API = "https://gitlab.com/api/v4"
HEADERS = (
    {"PRIVATE-TOKEN": os.getenv("GITLAB_TOKEN")} if os.getenv("GITLAB_TOKEN") else {}
)
STATE_FILE = "last_commit_state.json"
CHECKPOINT_DIR = "checkpoints"
os.makedirs(CHECKPOINT_DIR, exist_ok=True)
MAX_WORKERS = 8
MAX_RETRIES = 5
GITLAB_RATE_LIMIT = 429


# --- Utils ---
def load_json_file(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_json_file(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def load_state():
    print("📥 Loading state file...")
    return load_json_file(STATE_FILE)


def save_state(state):
    print("💾 Saving state file...")
    save_json_file(STATE_FILE, state)


def checkpoint_file(label, files):
    path = os.path.join(CHECKPOINT_DIR, f"{label}.json")
    print(f"📍 Writing checkpoint to {path}")
    save_json_file(path, files)


def load_checkpoint(label):
    path = os.path.join(CHECKPOINT_DIR, f"{label}.json")
    return load_json_file(path)


def safe_get(url, params=None, retries=MAX_RETRIES):
    backoff = 2
    for attempt in range(retries):
        print(f"🌐 GET {url} (Attempt {attempt + 1})")
        resp = requests.get(url, headers=HEADERS, params=params)
        if resp.status_code == GITLAB_RATE_LIMIT or resp.status_code >= 500:
            wait_time = backoff**attempt
            print(f"⚠️ HTTP {resp.status_code}. Retrying in {wait_time}s...")
            time.sleep(wait_time)
            continue
        resp.raise_for_status()
        return resp
    raise Exception(f"❌ Failed GET after {retries} attempts: {url}")


# --- GitLab API ---
def get_project_id(project_path):
    print(f"🔎 Resolving project ID for {project_path}")
    url = f"{GITLAB_API}/projects/{quote(project_path, safe='')}"
    return safe_get(url).json()["id"]


def get_commits(project_id, path, since=None):
    url = f"{GITLAB_API}/projects/{project_id}/repository/commits"
    params = {"path": path, "per_page": 100}
    if since:
        params["since"] = since
    print(f"📜 Fetching commits for {path}")
    return safe_get(url, params).json()


def get_commit_diff(project_id, commit_sha):
    url = f"{GITLAB_API}/projects/{project_id}/repository/commits/{commit_sha}/diff"
    print(f"📑 Fetching diff for commit {commit_sha}")
    return [f["new_path"] for f in safe_get(url).json()]


def get_tree_entries(project_id, path=""):
    url = f"{GITLAB_API}/projects/{project_id}/repository/tree"
    params = {"path": path, "per_page": 100}
    print(f"📂 Listing entries in {path}")
    return safe_get(url, params).json()


# --- Parallel BFS ---
def get_all_files_parallel(project_id, base_path, extensions, label):
    print(f"🚀 BFS for path: {base_path}")
    result = set(load_checkpoint(label))
    queue = [base_path] if base_path else [""]

    def worker(path):
        print(f"🔍 Exploring {path}")
        try:
            entries = get_tree_entries(project_id, path)
        except Exception as e:
            print(f"❌ Error fetching entries for {path}: {e}")
            return [], []

        files, dirs = [], []
        for e in entries:
            if e["type"] == "blob" and any(
                e["path"].endswith(ext) for ext in extensions
            ):
                print(f"📄 File found: {e['path']}")
                files.append(e["path"])
            elif e["type"] == "tree":
                dirs.append(e["path"])
        return files, dirs

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        while queue or futures:
            while queue and len(futures) < MAX_WORKERS:
                p = queue.pop(0)
                futures[executor.submit(worker, p)] = p

            done, _ = concurrent.futures.wait(
                futures, return_when=concurrent.futures.FIRST_COMPLETED
            )
            for f in done:
                try:
                    files, dirs = f.result()
                    result.update(files)
                    queue.extend(dirs)
                    checkpoint_file(label, list(result))
                except Exception as e:
                    print(f"❌ Worker failed: {e}")
                del futures[f]

    print(f"✅ BFS complete with {len(result)} files.")
    return sorted(result)


# --- Per Repo Logic ---
def process_repo(label, config, state):
    print(f"\n🔍 Processing {label.upper()}")
    project_id = get_project_id(config["path"])
    last_commit = state.get(label, {}).get("last_commit")
    changed_files = set()

    if last_commit:
        print(f"🧠 Last commit: {last_commit}")
        commits = get_commits(project_id, config["api_path"])
        new_commits = []
        for commit in commits:
            if commit["id"] == last_commit:
                break
            new_commits.append(commit)
        new_commits.reverse()

        for commit in new_commits:
            print(f"➡️ Commit: {commit['short_id']} - {commit['title']}")
            for f in get_commit_diff(project_id, commit["id"]):
                if f.startswith(config["subdir"]):
                    print(f"✅ Changed: {f}")
                    changed_files.add(f)

        if new_commits:
            state[label] = {"last_commit": new_commits[-1]["id"]}
    else:
        print("📦 No commit tracked yet — full walk")
        all_files = get_all_files_parallel(
            project_id, config["subdir"], config["extensions"], label
        )
        changed_files.update(all_files)
        latest = get_commits(project_id, config["api_path"])[0]
        state[label] = {"last_commit": latest["id"]}
        print(f"✅ Initial commit set to: {latest['id']}")

    return sorted(changed_files)


# --- Main ---
if __name__ == "__main__":
    print("🚀 Starting GitLab File Tracker")
    state = load_state()
    all_changes = {}

    for label, config in TRACKED_REPOS.items():
        try:
            changed = process_repo(label, config, state)
            all_changes[label] = changed
        except Exception as e:
            print(f"❌ Failed for {label}: {e}")

    save_state(state)

    print("\n📄 Changed Files Summary:")
    for label, files in all_changes.items():
        print(f"\n🔸 {label.upper()} ({len(files)} files)")
        for f in files:
            print(f" - {f}")
