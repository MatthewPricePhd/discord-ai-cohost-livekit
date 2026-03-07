"""
URL scraping functionality for Discord AI Co-Host Bot
"""
import asyncio
from typing import Dict, Any, Optional
from urllib.parse import urlparse, urljoin
import re

import requests
from bs4 import BeautifulSoup
import newspaper

from ..config import get_logger, settings

logger = get_logger(__name__)


class URLScraper:
    """Scrapes content from URLs for document processing"""
    
    def __init__(self):
        self.timeout = 30
        self.max_content_length = 5 * 1024 * 1024  # 5MB limit
        
        # User agent to avoid blocking
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    async def scrape_url(self, url: str) -> Dict[str, Any]:
        """
        Scrape content from a URL
        
        Args:
            url: The URL to scrape
            
        Returns:
            Dict containing scraped content and metadata
        """
        try:
            logger.info("Scraping URL", url=url)
            
            # Validate URL
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return {
                    "success": False,
                    "error": "Invalid URL format",
                    "url": url
                }
            
            # Try newspaper3k first (good for articles)
            article_result = await self._scrape_with_newspaper(url)
            if article_result["success"]:
                return article_result
            
            # Fallback to BeautifulSoup
            soup_result = await self._scrape_with_beautifulsoup(url)
            if soup_result["success"]:
                return soup_result
            
            return {
                "success": False,
                "error": "Failed to extract content from URL",
                "url": url
            }
            
        except Exception as e:
            logger.error("Error scraping URL", url=url, error=str(e))
            return {
                "success": False,
                "error": str(e),
                "url": url
            }
    
    async def _scrape_with_newspaper(self, url: str) -> Dict[str, Any]:
        """Scrape URL using newspaper3k library"""
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self._newspaper_scrape, url)
            return result
            
        except Exception as e:
            logger.debug("Newspaper3k scraping failed", url=url, error=str(e))
            return {
                "success": False,
                "error": str(e),
                "url": url
            }
    
    def _newspaper_scrape(self, url: str) -> Dict[str, Any]:
        """Internal newspaper scraping (runs in thread pool)"""
        try:
            article = newspaper3k.Article(url)
            article.download()
            article.parse()
            
            # Check if we got meaningful content
            if not article.text or len(article.text.strip()) < 100:
                return {
                    "success": False,
                    "error": "Insufficient content extracted",
                    "url": url
                }
            
            # Extract metadata
            metadata = {
                "title": article.title or "Untitled",
                "authors": article.authors,
                "publish_date": article.publish_date.isoformat() if article.publish_date else None,
                "summary": article.summary if hasattr(article, 'summary') else None,
                "keywords": list(article.keywords) if article.keywords else [],
                "source_url": url,
                "extraction_method": "newspaper3k"
            }
            
            logger.debug("Newspaper3k extraction successful",
                        url=url,
                        title=metadata["title"],
                        content_length=len(article.text))
            
            return {
                "success": True,
                "content": article.text,
                "title": metadata["title"],
                "metadata": metadata,
                "url": url
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "url": url
            }
    
    async def _scrape_with_beautifulsoup(self, url: str) -> Dict[str, Any]:
        """Scrape URL using BeautifulSoup as fallback"""
        try:
            # Make request
            response = requests.get(
                url, 
                headers=self.headers, 
                timeout=self.timeout,
                stream=True
            )
            
            response.raise_for_status()
            
            # Check content length
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.max_content_length:
                return {
                    "success": False,
                    "error": f"Content too large ({content_length} bytes)",
                    "url": url
                }
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title_tag = soup.find('title')
            title = title_tag.get_text().strip() if title_tag else "Untitled"
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
                element.decompose()
            
            # Try to find main content
            content = self._extract_main_content(soup)
            
            if not content or len(content.strip()) < 100:
                return {
                    "success": False,
                    "error": "Insufficient content extracted",
                    "url": url
                }
            
            # Extract metadata
            metadata = {
                "title": title,
                "source_url": url,
                "extraction_method": "beautifulsoup",
                "content_length": len(content)
            }
            
            # Try to extract description
            description_tag = soup.find('meta', attrs={'name': 'description'})
            if description_tag:
                metadata["description"] = description_tag.get('content', '').strip()
            
            # Try to extract keywords
            keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
            if keywords_tag:
                keywords = keywords_tag.get('content', '').strip()
                metadata["keywords"] = [k.strip() for k in keywords.split(',') if k.strip()]
            
            logger.debug("BeautifulSoup extraction successful",
                        url=url,
                        title=title,
                        content_length=len(content))
            
            return {
                "success": True,
                "content": content,
                "title": title,
                "metadata": metadata,
                "url": url
            }
            
        except requests.RequestException as e:
            logger.debug("BeautifulSoup request failed", url=url, error=str(e))
            return {
                "success": False,
                "error": f"Request failed: {str(e)}",
                "url": url
            }
        except Exception as e:
            logger.debug("BeautifulSoup parsing failed", url=url, error=str(e))
            return {
                "success": False,
                "error": str(e),
                "url": url
            }
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main content from HTML soup"""
        content_parts = []
        
        # Look for common content containers
        content_selectors = [
            'article',
            'main',
            '[role="main"]',
            '.content',
            '.main-content',
            '.post-content',
            '.entry-content',
            '.article-content',
            '#content',
            '#main-content'
        ]
        
        # Try each selector
        for selector in content_selectors:
            content_elements = soup.select(selector)
            if content_elements:
                for element in content_elements:
                    text = element.get_text(separator='\n', strip=True)
                    if text and len(text) > 200:  # Substantial content
                        content_parts.append(text)
                if content_parts:
                    break
        
        # If no specific content area found, extract from body
        if not content_parts:
            body = soup.find('body')
            if body:
                # Get paragraphs, headers, and list items
                text_elements = body.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'])
                for element in text_elements:
                    text = element.get_text(strip=True)
                    if text and len(text) > 20:  # Filter out very short text
                        content_parts.append(text)
        
        # Clean and combine content
        content = '\n\n'.join(content_parts)
        
        # Clean up whitespace
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = re.sub(r'[ \t]+', ' ', content)
        
        return content.strip()
    
    def is_valid_url(self, url: str) -> bool:
        """Check if URL is valid and accessible"""
        try:
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except Exception:
            return False
    
    async def get_url_metadata(self, url: str) -> Dict[str, Any]:
        """Get basic metadata from URL without full content scraping"""
        try:
            response = requests.head(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            metadata = {
                "url": url,
                "status_code": response.status_code,
                "content_type": response.headers.get('content-type', ''),
                "content_length": response.headers.get('content-length'),
                "last_modified": response.headers.get('last-modified'),
                "accessible": True
            }
            
            return metadata
            
        except Exception as e:
            return {
                "url": url,
                "accessible": False,
                "error": str(e)
            }