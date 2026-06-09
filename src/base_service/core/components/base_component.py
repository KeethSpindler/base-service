from abc import ABC, abstractmethod


class BaseComponent(ABC):
    """
    Component interface for all service components.

    Each component should implement the `initialize` method for setup and optionally 
    override `run` and `stop` for components with a long-running lifecycle.
    """

    @abstractmethod
    def initialize(self):
        """Initialize the component"""
        pass

    async def run(self) -> None:
        """Run the component. Override in subclasses that have a long-running lifecycle."""
        pass

    async def stop(self) -> None:
        """Stop the component. Override in subclasses that have a long-running lifecycle."""
        pass
