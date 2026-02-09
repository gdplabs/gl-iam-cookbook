"""Third-party OAuth connectors following the BOSA plugin pattern."""

from connectors.base import BaseConnector
from connectors.github import GitHubConnector

__all__ = ["BaseConnector", "GitHubConnector"]
