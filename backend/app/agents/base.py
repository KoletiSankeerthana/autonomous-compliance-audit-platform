"""Abstract base class for all compliance AI agents."""

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """
    All agents implement a single run() method that accepts a context dict
    and returns a result dict. This contract allows agents to be composed
    in LangGraph workflows without tight coupling.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable agent identifier used in logs."""
        ...

    @abstractmethod
    def run(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Execute the agent's task.

        Args:
            context: Input data from the workflow state.

        Returns:
            Result dict to be merged back into the workflow state.
        """
        ...
