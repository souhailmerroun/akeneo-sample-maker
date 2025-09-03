from abc import ABC, abstractmethod
from typing import List

class ImageSearchService(ABC):
    """Interface for image search services that return a list of image URLs."""
    
    @abstractmethod
    def name(self) -> str:
        """Return the name of the image search service."""
        ...

    @abstractmethod
    def image_urls(self, product_query: str, limit: int = 5) -> List[str]:
        """Return a list of image URLs based on the product query."""
        ...
