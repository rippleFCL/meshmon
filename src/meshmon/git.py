"""
Git repository management library using subprocess popen.

This library provides functionality to:
- Check if a repository needs updates
- Pull changes from remote with local reset
- Manage git operations safely
"""

import subprocess
from pathlib import Path

from structlog.stdlib import get_logger

logger = get_logger()


class GitError(Exception):
    """Custom exception for Git operations."""

    pass


class Repo:
    """Git repository manager using subprocess popen."""

    def __init__(
        self, git_uri: str, repo_path: str, remote: str = "origin", branch: str = "main"
    ):
        """
        Initialize Git repository manager.

        Args:
            git_uri: URI of the git repository
            repo_path: Path to the git repository
            remote: Remote name (default: origin)
            branch: Branch name (default: main)
        """
        self.git_uri = git_uri
        self.repo_path = Path(repo_path).resolve()
        self.remote = remote
        self.branch = branch

        if self.repo_path.exists() and not self._is_git_repo():
            raise GitError(f"Path {self.repo_path} is not a git repository")

    def _run_git_command(
        self, args: list, capture_output: bool = True, check: bool = True
    ) -> subprocess.CompletedProcess:
        cmd = ["git"] + args
        logger.debug("Running git command", cmd=cmd)

        try:
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=capture_output,
                text=True,
                check=check,
            )
            return result
        except subprocess.CalledProcessError as e:
            error_msg = f"Git command failed: {' '.join(cmd)}"
            if e.stderr:
                error_msg += f"\nError: {e.stderr.strip()}"
            raise GitError(error_msg) from e
        except FileNotFoundError as e:
            raise GitError(
                "Git command not found. Please ensure git is installed."
            ) from e

    def _is_git_repo(self) -> bool:
        """Check if the path is a git repository."""
        try:
            result = self._run_git_command(["rev-parse", "--git-dir"], check=False)
            return result.returncode == 0
        except Exception:
            return False

    def _get_current_commit_hash(self) -> str:
        """Get the current commit hash."""
        result = self._run_git_command(["rev-parse", "HEAD"])
        return result.stdout.strip()

    def _get_remote_commit_hash(self) -> str:
        """Get the remote commit hash for the tracking branch."""
        # Fetch to get latest remote info
        self._run_git_command(["fetch", self.remote])

        # Get remote commit hash
        result = self._run_git_command(["rev-parse", f"{self.remote}/{self.branch}"])
        return result.stdout.strip()

    def needs_update(self) -> bool:
        """
        Check if the repository needs to be updated.

        Returns:
            True if there are changes upstream, False otherwise

        Raises:
            GitError: If unable to check for updates
        """
        try:
            current_hash = self._get_current_commit_hash()
            remote_hash = self._get_remote_commit_hash()

            needs_update = current_hash != remote_hash
            return needs_update

        except Exception as e:
            raise GitError(f"Failed to check for updates: {e}") from e

    def reset_local_changes(self) -> None:
        logger.warning(
            "Resetting all local changes - this will discard uncommitted work"
        )

        # Reset to HEAD (discard staged and working directory changes)
        self._run_git_command(["reset", "--hard", "HEAD"])

        # Clean untracked files and directories
        self._run_git_command(["clean", "-fd"])

        logger.info("Local changes have been reset")

    def pull(self, reset_local: bool = True):
        try:
            self.reset_local_changes()
            self._run_git_command(["fetch", self.remote])
            self._run_git_command(["pull", self.remote, self.branch])
        except Exception as e:
            raise GitError(f"Failed to pull repository: {e}") from e

    def clone_or_update(self):
        if not self.repo_path.exists():
            # Clone repository
            parent_dir = self.repo_path.parent
            parent_dir.mkdir(parents=True, exist_ok=True)

            result = subprocess.run(
                ["git", "clone", self.git_uri, str(self.repo_path)],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                raise GitError(f"Failed to clone repository: {result.stderr}")
        else:
            # Update existing repository
            if self.needs_update():
                self.pull()
