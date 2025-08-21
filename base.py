from abc import ABC, abstractmethod
from typing import Optional

class ImageSearchService(ABC):
    """Minimal interface: just return the FIRST image URL (or None)."""

    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def first_image_url(self, product_query: str) -> Optional[str]:
        ...
