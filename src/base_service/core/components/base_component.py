from abc import ABC, abstractmethod


class BaseComponent(ABC):
    """
    Component interface for all service components.

    Components must initialize themselves. Long-running lifecycle methods are
    optional and are only called when overridden.
    """

    @abstractmethod
    def initialize(self) -> None:
        """Perform one-time component setup."""
        pass

    async def run(self) -> None:
        """Run the component when it has a long-running lifecycle."""
        pass

    async def stop(self) -> None:
        """Stop the component when it has a long-running lifecycle."""
        pass
