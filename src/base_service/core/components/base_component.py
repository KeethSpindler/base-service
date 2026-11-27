from abc import ABC, abstractmethod


class BaseComponent(ABC):
    """Interface for asynchronously managed service components."""

    @abstractmethod
    async def initialize(self) -> None:
        """Perform one-time component setup."""

    async def run(self) -> None:
        """Run the component when it owns a long-running task."""

    async def stop(self) -> None:
        """Release resources acquired during the component lifecycle."""
