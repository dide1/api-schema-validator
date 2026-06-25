import subprocess
from pathlib import Path

import pytest


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_git_status(client, git_repo: Path) -> None:
    response = client.get("/git/status")
    assert response.status_code == 200
    data = response.json()
    assert "branch" in data
    assert isinstance(data["staged"], list)
    assert isinstance(data["unstaged"], list)
    assert isinstance(data["untracked"], list)


def test_git_checkin(client, git_repo: Path) -> None:
    new_file = git_repo / "tracked.txt"
    new_file.write_text("hello\n", encoding="utf-8")

    response = client.post("/git/checkin", json={"message": "Add tracked file"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["commit_hash"]) == 40


def test_git_checkout_branch(client, git_repo: Path) -> None:
    _git(git_repo, "checkout", "-b", "feature")
    _git(git_repo, "checkout", "main")

    response = client.post("/git/checkout", json={"target": "feature"})
    assert response.status_code == 200
    assert response.json()["target"] == "feature"

    status = client.get("/git/status")
    assert status.json()["branch"] == "feature"
