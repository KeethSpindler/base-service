from enum import StrEnum, auto

from base_service.core.components.fastapi_component import FastAPIComponent


class ComponentRegistry(StrEnum):
    FASTAPI = auto()
