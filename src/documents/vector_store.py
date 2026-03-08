"""
Vector storage and retrieval for document chunks
"""
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMA_AVAILABLE = True
except Exception:
    CHROMA_AVAILABLE = False
    chromadb = None
    ChromaSettings = None  # type: ignore[assignment,misc]

from ..config import get_logger, settings

logger = get_logger(__name__)


class VectorStore:
    """Manages vector storage and retrieval for document chunks"""
    
    def __init__(self):
        self.client = None
        self.collection = None
        self.collection_name = "ai_cohost_documents"
        self.embedding_model = "text-embedding-3-small"  # OpenAI model
        self._init_attempted = False
    
    async def _ensure_initialized(self):
        """Lazily initialize the client on first use."""
        if not self._init_attempted:
            self._init_attempted = True
            await self._initialize_client()

    async def _initialize_client(self):
        """Initialize the vector database client"""
        try:
            if not CHROMA_AVAILABLE:
                logger.error("ChromaDB not available. Install with: pip install chromadb")
                return
            
            # Ensure directory exists
            settings.chroma_db_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(
                path=str(settings.chroma_db_path),
                settings=ChromaSettings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection(self.collection_name)
                logger.info("Connected to existing ChromaDB collection", 
                           collection=self.collection_name)
            except:
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "Document chunks for AI Co-Host Bot"}
                )
                logger.info("Created new ChromaDB collection", 
                           collection=self.collection_name)
            
            logger.info("Vector store initialized successfully")
            
        except Exception as e:
            logger.error("Failed to initialize vector store", error=str(e))
            self.client = None
            self.collection = None
    
    async def store_document(self,
                           document_id: str,
                           metadata: Dict[str, Any],
                           chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Store document chunks in vector database

        Args:
            document_id: Unique document identifier
            metadata: Document metadata
            chunks: List of text chunks with their data

        Returns:
            Dict with storage result
        """
        await self._ensure_initialized()
        try:
            if not self.collection:
                return {
                    "success": False,
                    "error": "Vector store not initialized"
                }
            
            if not chunks:
                return {
                    "success": False,
                    "error": "No chunks to store"
                }
            
            logger.debug("Storing document in vector store", 
                        document_id=document_id,
                        chunk_count=len(chunks))
            
            # Generate embeddings for all chunks
            chunk_texts = [chunk["text"] for chunk in chunks]
            embeddings = await self._generate_embeddings(chunk_texts)
            
            if not embeddings:
                return {
                    "success": False,
                    "error": "Failed to generate embeddings"
                }
            
            # Prepare data for storage
            chunk_ids = []
            chunk_metadatas = []
            
            for i, chunk in enumerate(chunks):
                chunk_id = f"{document_id}_chunk_{i}"
                chunk_ids.append(chunk_id)
                
                chunk_metadata = {
                    "document_id": document_id,
                    "chunk_index": i,
                    "start_char": chunk.get("start_char", 0),
                    "end_char": chunk.get("end_char", 0),
                    "char_count": chunk.get("char_count", len(chunk["text"])),
                    "document_title": metadata.get("title", ""),
                    "document_type": metadata.get("file_type", ""),
                    "source_url": metadata.get("source_url", "")
                }
                chunk_metadatas.append(chunk_metadata)
            
            # Store in ChromaDB
            self.collection.add(
                ids=chunk_ids,
                embeddings=embeddings,
                documents=chunk_texts,
                metadatas=chunk_metadatas
            )
            
            logger.info("Document stored in vector database",
                       document_id=document_id,
                       chunks_stored=len(chunks))
            
            return {
                "success": True,
                "chunks_stored": len(chunks),
                "document_id": document_id
            }
            
        except Exception as e:
            logger.error("Error storing document in vector store",
                        document_id=document_id,
                        error=str(e))
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_similar(self,
                           query: str,
                           n_results: int = 5,
                           document_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for similar document chunks

        Args:
            query: Search query text
            n_results: Number of results to return
            document_filter: Optional document ID to filter by

        Returns:
            List of similar chunks with metadata and scores
        """
        await self._ensure_initialized()
        try:
            if not self.collection:
                logger.warning("Vector store not initialized for search")
                return []
            
            # Generate query embedding
            query_embeddings = await self._generate_embeddings([query])
            if not query_embeddings:
                logger.warning("Failed to generate query embedding")
                return []
            
            query_embedding = query_embeddings[0]
            
            # Prepare search parameters
            search_params = {
                "query_embeddings": [query_embedding],
                "n_results": n_results
            }
            
            # Add document filter if specified
            if document_filter:
                search_params["where"] = {"document_id": document_filter}
            
            # Search in ChromaDB
            results = self.collection.query(**search_params)
            
            # Format results
            similar_chunks = []
            if results and results["ids"] and len(results["ids"]) > 0:
                for i in range(len(results["ids"][0])):
                    chunk_data = {
                        "id": results["ids"][0][i],
                        "text": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i] if "distances" in results else 0.0,
                        "similarity": 1.0 - results["distances"][0][i] if "distances" in results else 1.0
                    }
                    similar_chunks.append(chunk_data)
            
            logger.debug("Vector search completed",
                        query_length=len(query),
                        results_found=len(similar_chunks))
            
            return similar_chunks
            
        except Exception as e:
            logger.error("Error searching vector store", 
                        query=query[:100],
                        error=str(e))
            return []
    
    async def search_by_topics(self, 
                             topics: List[str], 
                             n_results_per_topic: int = 3) -> List[Dict[str, Any]]:
        """
        Search for chunks related to multiple topics
        
        Args:
            topics: List of topic strings
            n_results_per_topic: Number of results per topic
            
        Returns:
            List of relevant chunks, deduplicated and scored
        """
        try:
            all_results = []
            seen_chunk_ids = set()
            
            for topic in topics:
                topic_results = await self.search_similar(
                    query=topic,
                    n_results=n_results_per_topic
                )
                
                # Add topic relevance and deduplicate
                for result in topic_results:
                    if result["id"] not in seen_chunk_ids:
                        result["matched_topic"] = topic
                        all_results.append(result)
                        seen_chunk_ids.add(result["id"])
            
            # Sort by similarity score
            all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            
            logger.debug("Topic-based search completed",
                        topics=topics,
                        unique_results=len(all_results))
            
            return all_results
            
        except Exception as e:
            logger.error("Error in topic-based search", 
                        topics=topics,
                        error=str(e))
            return []
    
    async def delete_document(self, document_id: str) -> bool:
        """
        Delete all chunks for a document

        Args:
            document_id: Document ID to delete

        Returns:
            Success boolean
        """
        await self._ensure_initialized()
        try:
            if not self.collection:
                logger.warning("Vector store not initialized for deletion")
                return False
            
            # Find all chunks for the document
            results = self.collection.get(
                where={"document_id": document_id}
            )
            
            if results and results["ids"]:
                # Delete the chunks
                self.collection.delete(
                    ids=results["ids"]
                )
                
                logger.info("Document deleted from vector store",
                           document_id=document_id,
                           chunks_deleted=len(results["ids"]))
                return True
            else:
                logger.debug("No chunks found to delete", document_id=document_id)
                return True  # Nothing to delete is still success
                
        except Exception as e:
            logger.error("Error deleting document from vector store",
                        document_id=document_id,
                        error=str(e))
            return False
    
    async def get_document_chunks(self, document_id: str) -> List[Dict[str, Any]]:
        """Get all chunks for a specific document"""
        await self._ensure_initialized()
        try:
            if not self.collection:
                return []
            
            results = self.collection.get(
                where={"document_id": document_id}
            )
            
            chunks = []
            if results and results["ids"]:
                for i in range(len(results["ids"])):
                    chunk = {
                        "id": results["ids"][i],
                        "text": results["documents"][i],
                        "metadata": results["metadatas"][i]
                    }
                    chunks.append(chunk)
            
            # Sort by chunk index
            chunks.sort(key=lambda x: x["metadata"].get("chunk_index", 0))
            
            return chunks
            
        except Exception as e:
            logger.error("Error getting document chunks",
                        document_id=document_id,
                        error=str(e))
            return []
    
    async def _generate_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Generate embeddings using OpenAI API"""
        try:
            from ..api.openai_client import OpenAIClient
            
            # Create a temporary OpenAI client for embeddings
            # In a real implementation, this would be injected or shared
            openai_client = OpenAIClient()
            
            embeddings = await openai_client.generate_embeddings(texts)
            
            logger.debug("Generated embeddings", 
                        text_count=len(texts),
                        embedding_count=len(embeddings))
            
            return embeddings
            
        except Exception as e:
            logger.error("Error generating embeddings", error=str(e))
            return None
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector collection"""
        try:
            if not self.collection:
                return {"error": "Collection not initialized"}
            
            count = self.collection.count()
            
            # Get sample of documents to analyze
            sample = self.collection.get(limit=10)
            
            unique_docs = set()
            if sample and sample["metadatas"]:
                for metadata in sample["metadatas"]:
                    unique_docs.add(metadata.get("document_id", "unknown"))
            
            return {
                "total_chunks": count,
                "sample_documents": len(unique_docs),
                "collection_name": self.collection_name,
                "initialized": True
            }
            
        except Exception as e:
            logger.error("Error getting collection stats", error=str(e))
            return {"error": str(e), "initialized": False}