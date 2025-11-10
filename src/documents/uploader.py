"""
Document upload handler for Discord AI Co-Host Bot
"""
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, BinaryIO
from datetime import datetime

from fastapi import UploadFile

from .processor import DocumentProcessor
from .vector_store import VectorStore
from ..config import get_logger, settings

logger = get_logger(__name__)


class DocumentUploader:
    """Handles document uploads and processing"""
    
    def __init__(self):
        self.processor = DocumentProcessor()
        self.vector_store = VectorStore()
        self.upload_dir = settings.upload_dir
        self.max_file_size = settings.max_file_size
        self.supported_formats = set(f".{fmt}" for fmt in settings.supported_formats)
        
        # Ensure upload directory exists
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Document registry (in production, this would be a database)
        self.documents: Dict[str, Dict[str, Any]] = {}
    
    async def upload_document(self, 
                            file: UploadFile, 
                            title: Optional[str] = None,
                            metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Upload and process a document file
        
        Args:
            file: The uploaded file
            title: Optional title for the document
            metadata: Additional metadata
            
        Returns:
            Dict with upload result and document information
        """
        try:
            # Validate file
            validation_result = await self._validate_file(file)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "error": validation_result["error"],
                    "document_id": None
                }
            
            # Save file to disk
            saved_path = await self._save_file(file)
            
            # Prepare processing metadata
            processing_metadata = metadata or {}
            if title:
                processing_metadata["title"] = title
            
            # Process document
            result = await self.processor.process_document(saved_path, processing_metadata)
            
            if not result["success"]:
                # Clean up saved file on processing failure
                if saved_path.exists():
                    saved_path.unlink()
                return result
            
            # Store in vector database
            vector_result = await self._store_in_vector_db(result)
            if not vector_result["success"]:
                # Clean up on vector storage failure
                if saved_path.exists():
                    saved_path.unlink()
                return {
                    "success": False,
                    "error": f"Failed to store vectors: {vector_result['error']}",
                    "document_id": result["document_id"]
                }
            
            # Register document
            doc_info = {
                **result["metadata"],
                "file_path": str(saved_path),
                "upload_time": datetime.utcnow().isoformat(),
                "vector_stored": True
            }
            
            self.documents[result["document_id"]] = doc_info
            
            logger.info("Document uploaded successfully",
                       document_id=result["document_id"],
                       filename=file.filename,
                       chunks=len(result["chunks"]))
            
            return {
                "success": True,
                "document_id": result["document_id"],
                "metadata": doc_info,
                "chunks_created": len(result["chunks"]),
                "message": f"Successfully uploaded and processed '{file.filename}'"
            }
            
        except Exception as e:
            logger.error("Error uploading document", 
                        filename=file.filename,
                        error=str(e))
            return {
                "success": False,
                "error": str(e),
                "document_id": None
            }
    
    async def upload_from_url(self, 
                            url: str, 
                            title: Optional[str] = None,
                            metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Upload content from a URL
        
        Args:
            url: The URL to scrape
            title: Optional title for the content
            metadata: Additional metadata
            
        Returns:
            Dict with upload result and document information
        """
        try:
            from .url_scraper import URLScraper
            
            scraper = URLScraper()
            scrape_result = await scraper.scrape_url(url)
            
            if not scrape_result["success"]:
                return {
                    "success": False,
                    "error": scrape_result["error"],
                    "document_id": None
                }
            
            # Process the scraped content
            content_title = title or scrape_result["title"]
            processing_metadata = metadata or {}
            processing_metadata.update({
                "source_url": url,
                "scraped_at": datetime.utcnow().isoformat()
            })
            
            result = await self.processor.process_url_content(
                url=url,
                content=scrape_result["content"],
                title=content_title
            )
            
            if not result["success"]:
                return result
            
            # Store in vector database
            vector_result = await self._store_in_vector_db(result)
            if not vector_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to store vectors: {vector_result['error']}",
                    "document_id": result["document_id"]
                }
            
            # Register document
            doc_info = {
                **result["metadata"],
                "upload_time": datetime.utcnow().isoformat(),
                "vector_stored": True,
                "scraped_content": True
            }
            
            self.documents[result["document_id"]] = doc_info
            
            logger.info("URL content uploaded successfully",
                       document_id=result["document_id"],
                       url=url,
                       chunks=len(result["chunks"]))
            
            return {
                "success": True,
                "document_id": result["document_id"],
                "metadata": doc_info,
                "chunks_created": len(result["chunks"]),
                "message": f"Successfully scraped and processed content from '{url}'"
            }
            
        except Exception as e:
            logger.error("Error uploading from URL", 
                        url=url,
                        error=str(e))
            return {
                "success": False,
                "error": str(e),
                "document_id": None
            }
    
    async def delete_document(self, document_id: str) -> Dict[str, Any]:
        """
        Delete a document and its associated data
        
        Args:
            document_id: The document ID to delete
            
        Returns:
            Dict with deletion result
        """
        try:
            if document_id not in self.documents:
                return {
                    "success": False,
                    "error": f"Document {document_id} not found"
                }
            
            doc_info = self.documents[document_id]
            
            # Remove from vector store
            await self.vector_store.delete_document(document_id)
            
            # Remove file if it exists
            if "file_path" in doc_info:
                file_path = Path(doc_info["file_path"])
                if file_path.exists():
                    file_path.unlink()
                    logger.debug("Deleted file", file_path=str(file_path))
            
            # Remove from registry
            del self.documents[document_id]
            
            logger.info("Document deleted successfully", document_id=document_id)
            
            return {
                "success": True,
                "message": f"Document {document_id} deleted successfully"
            }
            
        except Exception as e:
            logger.error("Error deleting document", 
                        document_id=document_id,
                        error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
    
    def list_documents(self) -> List[Dict[str, Any]]:
        """
        List all uploaded documents
        
        Returns:
            List of document metadata
        """
        documents = []
        for doc_id, doc_info in self.documents.items():
            # Create a clean summary for listing
            summary = {
                "id": doc_id,
                "title": doc_info.get("title", "Untitled"),
                "filename": doc_info.get("filename"),
                "file_type": doc_info.get("file_type"),
                "file_size": doc_info.get("file_size"),
                "chunk_count": doc_info.get("chunk_count", 0),
                "upload_time": doc_info.get("upload_time"),
                "source_url": doc_info.get("source_url")  # For URL-based documents
            }
            documents.append(summary)
        
        # Sort by upload time (newest first)
        documents.sort(key=lambda x: x.get("upload_time", ""), reverse=True)
        
        return documents
    
    def get_document_info(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a document"""
        return self.documents.get(document_id)
    
    async def _validate_file(self, file: UploadFile) -> Dict[str, Any]:
        """Validate uploaded file"""
        if not file.filename:
            return {"valid": False, "error": "No filename provided"}
        
        # Check file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in self.supported_formats:
            return {
                "valid": False,
                "error": f"Unsupported file type {file_ext}. Supported: {', '.join(self.supported_formats)}"
            }
        
        # Check file size
        file.file.seek(0, 2)  # Seek to end
        file_size = file.file.tell()
        file.file.seek(0)  # Reset to beginning
        
        if file_size > self.max_file_size:
            return {
                "valid": False,
                "error": f"File too large ({file_size} bytes). Maximum: {self.max_file_size} bytes"
            }
        
        if file_size == 0:
            return {"valid": False, "error": "File is empty"}
        
        return {"valid": True, "file_size": file_size}
    
    async def _save_file(self, file: UploadFile) -> Path:
        """Save uploaded file to disk"""
        # Generate unique filename
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        safe_filename = "".join(c for c in file.filename if c.isalnum() or c in "._-")
        unique_filename = f"{timestamp}_{safe_filename}"
        
        file_path = self.upload_dir / unique_filename
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.debug("File saved", 
                    original_name=file.filename,
                    saved_path=str(file_path))
        
        return file_path
    
    async def _store_in_vector_db(self, processing_result: Dict[str, Any]) -> Dict[str, Any]:
        """Store document chunks in vector database"""
        try:
            document_id = processing_result["document_id"]
            metadata = processing_result["metadata"]
            chunks = processing_result["chunks"]
            
            # Store document and chunks
            result = await self.vector_store.store_document(
                document_id=document_id,
                metadata=metadata,
                chunks=chunks
            )
            
            return result
            
        except Exception as e:
            logger.error("Error storing in vector database", error=str(e))
            return {
                "success": False,
                "error": str(e)
            }