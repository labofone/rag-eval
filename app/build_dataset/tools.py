"""
Tools for the buildDataset feature, including web search, PDF downloading,
and interacting with a Playwright MCP server for web scraping.
"""
import httpx
from typing import List, Dict, Optional, Any
from pathlib import Path
import logging

from .config import settings
from .schemas import InitialSearchResult # For type hinting if needed

# Configure logging for this module
logger = logging.getLogger(__name__)
# Example: logger.info("Fetching data from SerpAPI")

def search_academic_papers_serpapi(
    query: str,
    num_results: int = 10
) -> List[Dict[str, Any]]:
    """
    Performs an academic paper search using SerpAPI.

    Args:
        query: The search query.
        num_results: The number of results to fetch.

    Returns:
        A list of search result dictionaries from SerpAPI.
        Returns an empty list if the API key is not configured or an error occurs.
    """
    if not settings.SERPAPI_API_KEY:
        logger.error("SerpAPI API key not configured. Cannot perform search.")
        return []

    try:
        from serpapi import GoogleSearch
        params = {
            "engine": "google_scholar",
            "q": query,
            "api_key": settings.SERPAPI_API_KEY,
            "num": str(num_results),
            # "hl": "en", # Language
            # "as_ylo": "2020" # Example: articles published since 2020
        }
        search = GoogleSearch(params)
        results = search.get_dict()

        organic_results = results.get("organic_results", [])
        if not organic_results:
            logger.warning(f"No organic results found for query: {query}")
            # Check for error messages from SerpAPI
            if "error" in results:
                 logger.error(f"SerpAPI error: {results['error']}")
            return []

        logger.info(f"SerpAPI returned {len(organic_results)} results for query: {query}")
        return organic_results

    except ImportError:
        logger.error("SerpAPI client (serpapi) not installed. Please install it: pip install google-search-results")
        return []
    except Exception as e:
        logger.error(f"Error during SerpAPI search for '{query}': {e}")
        return []

async def download_pdf_async(
    url: str,
    output_dir: Path,
    file_name: Optional[str] = None
) -> Optional[Path]:
    """
    Asynchronously downloads a PDF from a given URL.

    Args:
        url: The URL of the PDF to download.
        output_dir: The directory to save the downloaded PDF.
        file_name: Optional name for the PDF file. If None, uses the last part of the URL.

    Returns:
        The Path to the downloaded PDF, or None if download fails.
    """
    if not file_name:
        file_name = Path(url).name
        if not file_name.lower().endswith(".pdf"):
            file_name += ".pdf" # Ensure it has a .pdf extension

    output_path = output_dir / file_name
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client: # Increased timeout
            logger.info(f"Attempting to download PDF from: {url}")
            response = await client.get(url)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

            content_type = response.headers.get("content-type", "").lower()
            if "application/pdf" not in content_type:
                logger.warning(f"URL {url} did not return a PDF. Content-Type: {content_type}. Skipping download.")
                # Optionally, save the content anyway if it might be useful, or handle as error
                # For now, we strictly expect PDF
                return None

            with open(output_path, "wb") as f:
                f.write(response.content)
            logger.info(f"Successfully downloaded PDF to: {output_path}")
            return output_path
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error downloading PDF from {url}: {e.response.status_code} - {e.response.text[:200]}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Request error downloading PDF from {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading PDF from {url}: {e}")
        return None

async def fetch_webpage_content(url: str) -> Optional[str]:
    """
    Fetches the main content of a webpage, initially using a Playwright MCP server.

    Args:
        url: The URL of the webpage to scrape.

    Returns:
        The extracted main content as a string, or None if an error occurs or MCP is not configured.
    """
    if not settings.PLAYWRIGHT_MCP_URL:
        logger.warning("Playwright MCP URL not configured. Cannot fetch webpage content.")
        return None

    try:
        async with httpx.AsyncClient(timeout=60.0) as client: # Increased timeout for potentially long scrapes
            logger.info(f"Fetching webpage content from {url} via Playwright MCP: {settings.PLAYWRIGHT_MCP_URL}")
            response = await client.post(settings.PLAYWRIGHT_MCP_URL, json={"url": url})
            response.raise_for_status()

            data = response.json()
            if data.get("status") == "success" and "content" in data:
                logger.info(f"Successfully fetched content for {url} via Playwright MCP.")
                return data["content"]
            else:
                error_message = data.get("error", "Unknown error from Playwright MCP")
                logger.error(f"Playwright MCP failed for {url}: {error_message}")
                return None
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error calling Playwright MCP for {url}: {e.response.status_code} - {e.response.text[:200]}")
        return None
    except httpx.RequestError as e:
        logger.error(f"Request error calling Playwright MCP for {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error calling Playwright MCP for {url}: {e}")
        return None

# Example usage (for testing purposes, typically called from the agent/graph)
# if __name__ == "__main__":
#     import asyncio
#     # Ensure .env is loaded if running directly for testing
#     # from dotenv import load_dotenv
#     # load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

#     async def test_serpapi():
#         print("Testing SerpAPI...")
#         results = search_academic_papers_serpapi("RAG evaluation techniques", num_results=2)
#         if results:
#             for res in results:
#                 print(f"- Title: {res.get('title')}, Link: {res.get('link')}")
#         else:
#             print("SerpAPI test failed or returned no results.")

#     async def test_pdf_download():
#         print("\nTesting PDF Download...")
#         # Replace with a real, stable PDF URL for testing
#         pdf_url = "https://arxiv.org/pdf/1706.03762.pdf" # Example: "Attention Is All You Need"
#         temp_dir = Path("./temp_downloads")
#         downloaded_path = await download_pdf_async(pdf_url, temp_dir)
#         if downloaded_path:
#             print(f"PDF downloaded to: {downloaded_path}")
#             # downloaded_path.unlink() # Clean up
#             # temp_dir.rmdir()
#         else:
#             print("PDF download test failed.")

#     async def test_playwright_mcp():
#         print("\nTesting Playwright MCP...")
#         # Replace with a URL you want to test scraping
#         # Ensure your Playwright MCP server is running and configured in .env
#         if settings.PLAYWRIGHT_MCP_URL:
#             test_url = "https://blog.langchain.dev/langgraph-cloud/"
#             content = await fetch_webpage_content(test_url) # Updated function name here
#             if content:
#                 print(f"Content fetched for {test_url}:\n{content[:500]}...") # Print first 500 chars
#             else:
#                 print(f"Playwright MCP test failed for {test_url}.")
#         else:
#             print("Playwright MCP URL not configured, skipping test.")

#     async def main_tests():
#         await test_serpapi()
#         # await test_pdf_download() # Uncomment to test
#         # await test_playwright_mcp() # Uncomment to test

#     if settings.SERPAPI_API_KEY: # Only run if key is present
#        asyncio.run(main_tests())
#     else:
#        print("SERPAPI_API_KEY not found in .env. Skipping direct tool tests.")
