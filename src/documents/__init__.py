"""
Document processing module for Discord AI Co-Host Bot

Imports are lazy to avoid triggering chromadb import at module level
(chromadb has pydantic v1 shim issues on Python 3.14).
"""


def __getattr__(name: str):
    if name == "DocumentUploader":
        from .uploader import DocumentUploader
        return DocumentUploader
    if name == "DocumentProcessor":
        from .processor import DocumentProcessor
        return DocumentProcessor
    if name == "URLScraper":
        from .url_scraper import URLScraper
        return URLScraper
    if name == "VectorStore":
        from .vector_store import VectorStore
        return VectorStore
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["DocumentUploader", "DocumentProcessor", "URLScraper", "VectorStore"]
