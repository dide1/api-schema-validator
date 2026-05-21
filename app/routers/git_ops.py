from fastapi import APIRouter

from app.models.schemas import (
    GitCheckinRequest,
    GitCheckinResponse,
    GitCheckoutRequest,
    GitCheckoutResponse,
    GitStatusResponse,
)
from app.services import git_service

router = APIRouter(prefix="/git", tags=["git"])


@router.post("/checkin", response_model=GitCheckinResponse)
def git_checkin(body: GitCheckinRequest) -> GitCheckinResponse:
    commit_hash = git_service.checkin(body.message)
    return GitCheckinResponse(success=True, commit_hash=commit_hash)


@router.post("/checkout", response_model=GitCheckoutResponse)
def git_checkout(body: GitCheckoutRequest) -> GitCheckoutResponse:
    target = git_service.checkout(body.target)
    return GitCheckoutResponse(success=True, target=target)


@router.get("/status", response_model=GitStatusResponse)
def git_status() -> GitStatusResponse:
    data = git_service.status()
    return GitStatusResponse(
        branch=str(data["branch"]),
        staged=list(data["staged"]),
        unstaged=list(data["unstaged"]),
        untracked=list(data["untracked"]),
    )
