"""
Document retrieval system for context enhancement
"""
from typing import List, Dict, Any, Optional, Tuple

from ..documents.vector_store import VectorStore
from ..config import get_logger

logger = get_logger(__name__)


class DocumentRetriever:
    """Retrieves relevant document chunks based on conversation context"""
    
    def __init__(self):
        self.vector_store = VectorStore()
        self.max_chunks_per_query = 3
        self.similarity_threshold = 0.7
        self.max_total_chunks = 8
    
    async def get_relevant_documents(self, 
                                   topics: List[str], 
                                   conversation_context: str = "",
                                   max_chunks: int = None) -> List[Dict[str, Any]]:
        """
        Retrieve document chunks relevant to current conversation topics
        
        Args:
            topics: List of current conversation topics
            conversation_context: Recent conversation text for context
            max_chunks: Maximum chunks to return (overrides default)
            
        Returns:
            List of relevant document chunks with metadata
        """
        try:
            if not topics:
                return []
            
            max_chunks = max_chunks or self.max_total_chunks
            all_results = []
            seen_chunk_ids = set()
            
            # Search for each topic
            for topic in topics:
                topic_results = await self.vector_store.search_similar(
                    query=topic,
                    n_results=self.max_chunks_per_query
                )
                
                # Filter by similarity threshold and deduplicate
                for result in topic_results:
                    if (result.get("similarity", 0) >= self.similarity_threshold and 
                        result["id"] not in seen_chunk_ids):
                        
                        result["matched_topic"] = topic
                        all_results.append(result)
                        seen_chunk_ids.add(result["id"])
            
            # If we have conversation context, also search with that
            if conversation_context and len(conversation_context) > 100:
                context_results = await self.vector_store.search_similar(
                    query=conversation_context,
                    n_results=self.max_chunks_per_query
                )
                
                for result in context_results:
                    if (result.get("similarity", 0) >= self.similarity_threshold and 
                        result["id"] not in seen_chunk_ids):
                        
                        result["matched_topic"] = "conversation_context"
                        all_results.append(result)
                        seen_chunk_ids.add(result["id"])
            
            # Sort by relevance score (similarity)
            all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            
            # Limit results
            final_results = all_results[:max_chunks]
            
            # Enhance results with additional context
            enhanced_results = await self._enhance_results(final_results)
            
            logger.debug("Document retrieval completed",
                        topics=topics,
                        total_found=len(all_results),
                        returned=len(enhanced_results))
            
            return enhanced_results
            
        except Exception as e:
            logger.error("Error retrieving relevant documents", 
                        topics=topics,
                        error=str(e))
            return []
    
    async def search_documents(self, 
                             query: str, 
                             document_filter: Optional[str] = None,
                             n_results: int = 5) -> List[Dict[str, Any]]:
        """
        Direct search in document collection
        
        Args:
            query: Search query
            document_filter: Optional document ID to filter by
            n_results: Number of results to return
            
        Returns:
            List of matching document chunks
        """
        try:
            results = await self.vector_store.search_similar(
                query=query,
                n_results=n_results,
                document_filter=document_filter
            )
            
            # Filter by similarity threshold
            filtered_results = [
                result for result in results
                if result.get("similarity", 0) >= self.similarity_threshold
            ]
            
            return await self._enhance_results(filtered_results)
            
        except Exception as e:
            logger.error("Error searching documents", 
                        query=query,
                        error=str(e))
            return []
    
    async def get_document_summary(self, document_id: str) -> Optional[str]:
        """
        Get a summary of a specific document
        
        Args:
            document_id: The document ID
            
        Returns:
            Document summary or None if not found
        """
        try:
            # Get all chunks for the document
            chunks = await self.vector_store.get_document_chunks(document_id)
            
            if not chunks:
                return None
            
            # Combine chunks to form document text
            full_text = "\n\n".join([chunk["text"] for chunk in chunks])
            
            # Create summary using AI (if available)
            try:
                from ..api.openai_client import OpenAIClient
                client = OpenAIClient()
                summary = await client.generate_context_summary(full_text, max_tokens=500)
                return summary
            except:
                # Fallback to simple truncation
                return full_text[:1000] + "..." if len(full_text) > 1000 else full_text
                
        except Exception as e:
            logger.error("Error getting document summary", 
                        document_id=document_id,
                        error=str(e))
            return None
    
    async def get_context_enhanced_chunks(self, 
                                        chunks: List[Dict[str, Any]], 
                                        conversation_topics: List[str]) -> List[Dict[str, Any]]:
        """
        Enhance document chunks with conversation context
        
        Args:
            chunks: List of document chunks
            conversation_topics: Current conversation topics
            
        Returns:
            Enhanced chunks with context information
        """
        try:
            if not chunks or not conversation_topics:
                return chunks
            
            enhanced_chunks = []
            
            for chunk in chunks:
                enhanced_chunk = chunk.copy()
                
                # Calculate topic relevance
                chunk_text = chunk.get("text", "").lower()
                topic_matches = []
                
                for topic in conversation_topics:
                    if topic.lower() in chunk_text:
                        topic_matches.append(topic)
                
                enhanced_chunk["topic_matches"] = topic_matches
                enhanced_chunk["topic_relevance"] = len(topic_matches) / len(conversation_topics)
                
                # Add context hints
                enhanced_chunk["context_hint"] = self._generate_context_hint(chunk, conversation_topics)
                
                enhanced_chunks.append(enhanced_chunk)
            
            # Sort by topic relevance
            enhanced_chunks.sort(key=lambda x: x.get("topic_relevance", 0), reverse=True)
            
            return enhanced_chunks
            
        except Exception as e:
            logger.error("Error enhancing chunks with context", error=str(e))
            return chunks
    
    async def _enhance_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Add additional context and metadata to results"""
        try:
            enhanced_results = []
            
            for result in results:
                enhanced_result = result.copy()
                
                # Add document information
                metadata = result.get("metadata", {})
                enhanced_result["document_title"] = metadata.get("document_title", "Unknown Document")
                enhanced_result["document_type"] = metadata.get("document_type", "unknown")
                enhanced_result["chunk_index"] = metadata.get("chunk_index", 0)
                
                # Add relevance explanation
                enhanced_result["relevance_reason"] = self._explain_relevance(result)
                
                # Truncate text if too long for context
                text = result.get("text", "")
                if len(text) > 500:
                    enhanced_result["text_preview"] = text[:500] + "..."
                    enhanced_result["full_text"] = text
                else:
                    enhanced_result["text_preview"] = text
                
                enhanced_results.append(enhanced_result)
            
            return enhanced_results
            
        except Exception as e:
            logger.error("Error enhancing results", error=str(e))
            return results
    
    def _explain_relevance(self, result: Dict[str, Any]) -> str:
        """Generate explanation for why this result is relevant"""
        try:
            similarity = result.get("similarity", 0)
            matched_topic = result.get("matched_topic", "")
            
            if matched_topic == "conversation_context":
                return f"Matches current conversation context (similarity: {similarity:.2f})"
            elif matched_topic:
                return f"Relevant to topic '{matched_topic}' (similarity: {similarity:.2f})"
            else:
                return f"General relevance (similarity: {similarity:.2f})"
                
        except Exception:
            return "Relevant to current discussion"
    
    def _generate_context_hint(self, chunk: Dict[str, Any], topics: List[str]) -> str:
        """Generate a hint about how this chunk relates to current topics"""
        try:
            chunk_text = chunk.get("text", "").lower()
            matching_topics = [topic for topic in topics if topic.lower() in chunk_text]
            
            if matching_topics:
                if len(matching_topics) == 1:
                    return f"This discusses {matching_topics[0]}"
                else:
                    return f"This covers {', '.join(matching_topics[:2])} and more"
            else:
                return "This provides relevant background information"
                
        except Exception:
            return "Relevant to current discussion"
    
    async def get_retrieval_stats(self) -> Dict[str, Any]:
        """Get statistics about document retrieval performance"""
        try:
            vector_stats = self.vector_store.get_collection_stats()
            
            return {
                "vector_store_stats": vector_stats,
                "similarity_threshold": self.similarity_threshold,
                "max_chunks_per_query": self.max_chunks_per_query,
                "max_total_chunks": self.max_total_chunks
            }
            
        except Exception as e:
            logger.error("Error getting retrieval stats", error=str(e))
            return {"error": str(e)}
    
    def update_retrieval_settings(self, 
                                similarity_threshold: Optional[float] = None,
                                max_chunks: Optional[int] = None) -> None:
        """Update retrieval settings"""
        try:
            if similarity_threshold is not None:
                self.similarity_threshold = max(0.0, min(1.0, similarity_threshold))
                logger.info("Updated similarity threshold", threshold=self.similarity_threshold)
            
            if max_chunks is not None:
                self.max_total_chunks = max(1, min(20, max_chunks))
                logger.info("Updated max chunks", max_chunks=self.max_total_chunks)
                
        except Exception as e:
            logger.error("Error updating retrieval settings", error=str(e))


async def retrieve_relevant_docs(topics: List[str], vector_store, k: int = 5) -> List[Dict[str, Any]]:
    """
    Module-level convenience function to query a vector store for relevant docs.

    Queries the vector store for each topic, deduplicates by chunk ID,
    ranks by relevance score, and returns the top-k results.

    Args:
        topics: List of topic strings to search for
        vector_store: A vector store instance with a search_similar method
        k: Number of top results to return (default 5)

    Returns:
        List of document chunk dicts sorted by relevance
    """
    if not topics:
        return []

    all_results: List[Dict[str, Any]] = []
    seen_ids: set = set()

    for topic in topics:
        try:
            results = await vector_store.search_similar(query=topic, n_results=k)
        except Exception as e:
            logger.error("Error querying vector store for topic", topic=topic, error=str(e))
            continue

        for result in results:
            chunk_id = result.get("id")
            if chunk_id and chunk_id in seen_ids:
                continue
            if chunk_id:
                seen_ids.add(chunk_id)
            result["matched_topic"] = topic
            all_results.append(result)

    all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
    return all_results[:k]