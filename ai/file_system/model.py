

from dataclasses import dataclass
from typing import Optional


@dataclass
class FileSearchMatch:
    """Represents a single search result within a file system."""

    path: str
    snippet: Optional[str] = None


@dataclass
class CommandResult:
    """Represents the result of executing a shell command."""

    stdout: str
    stderr: str
    returncode: int