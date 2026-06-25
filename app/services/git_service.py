from git import Repo
from git.exc import BadName, GitCommandError, InvalidGitRepositoryError

from app.config import REPO_PATH


def _get_repo() -> Repo:
    try:
        return Repo(REPO_PATH)
    except InvalidGitRepositoryError as exc:
        raise GitCommandError(
            ["git"],
            128,
            stderr=f"Not a git repository: {REPO_PATH}. Run 'git init' in the project root.",
        ) from exc


def checkin(message: str) -> str:
    repo = _get_repo()
    try:
        repo.git.add(A=True)
        commit = repo.index.commit(message)
        return commit.hexsha
    except GitCommandError as exc:
        raise exc


def checkout(target: str) -> str:
    repo = _get_repo()
    try:
        repo.git.checkout(target)
        return target
    except GitCommandError as exc:
        raise exc


def status() -> dict[str, str | list[str]]:
    repo = _get_repo()
    try:
        try:
            branch = repo.active_branch.name
        except TypeError:
            branch = "HEAD (detached)"

        try:
            staged = [
                item.a_path or item.b_path or ""
                for item in repo.index.diff("HEAD")
            ]
        except BadName:
            staged = []
        unstaged = [
            item.a_path or item.b_path or ""
            for item in repo.index.diff(None)
        ]
        untracked = list(repo.untracked_files)

        return {
            "branch": branch,
            "staged": [p for p in staged if p],
            "unstaged": [p for p in unstaged if p],
            "untracked": untracked,
        }
    except GitCommandError as exc:
        raise exc
