from abc import ABC, abstractmethod


class BaseComponent(ABC):
    """
    Component interface for all service components.

    Each component should implement the `run` and `stop` for components with a long-running lifecycle.
    """

    @abstractmethod
    async def run(self) -> None:
        """Run the component."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Stop the component."""
        pass
