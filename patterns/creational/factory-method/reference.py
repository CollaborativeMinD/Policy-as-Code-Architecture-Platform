"""RDP-C03 factory method dispatches approved concrete creators only."""

from __future__ import annotations

from abc import ABC, abstractmethod
from .contracts import Product, Request


class Creator(ABC):
    @abstractmethod
    def create(self, text: str) -> Product:
        raise NotImplementedError


class EchoCreator(Creator):
    def create(self, text: str) -> Product:
        return Product(text=text)


class UppercaseCreator(Creator):
    def create(self, text: str) -> Product:
        return Product(text=text.upper())


def create(request: Request) -> Product:
    creators = {"echo": EchoCreator, "uppercase": UppercaseCreator}
    return creators[request.provider]().create(request.text)
