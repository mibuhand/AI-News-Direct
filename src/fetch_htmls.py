import asyncio
import httpx
import json
from pathlib import Path
import re
from datetime import datetime, timezone
from urllib.parse import urljoin
import logging

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define directories for caching HTML files and logs
script_dir = Path(__file__).resolve().parent
project_dir = script_dir.parent
html_cache_dir = project_dir / "html_cache"
logs_dir = project_dir / "logs"

# Ensure the cache and logs directories exist
html_cache_dir.mkdir(exist_ok=True)
logs_dir.mkdir(exist_ok=True)


async def fetch_and_save(client, url_data, semaphore):
    """
    Fetches a URL and saves the HTML content to a file.

    Args:
        client (httpx.AsyncClient): The HTTP client used for making requests.
        url_data (dict): A dictionary containing 'base_url', 'domain', and 'page'.
        semaphore (asyncio.Semaphore): A semaphore to limit concurrent requests.

    Returns:
        dict: A dictionary with the URL, status, and file name or error details.
    """
    async with semaphore:
        try:
            # Construct the full URL
            url = urljoin(url_data['base_url'].rstrip('/')+'/', url_data['page'])
            response = await client.get(url)

            # Use domain and page from JSON data to construct filename
            domain = re.sub(r'[^\w]', '_', url_data['domain'])
            page = re.sub(r'[^\w]', '_', url_data['page'].replace('/', '_'))

            # Ensure the filename is in "domain_page" format
            if not page:
                page = 'index'  # Default to 'index' if no specific page path is provided

            filename = f"{domain}_{page}"

            # Save the HTML content to a file
            with open(html_cache_dir / f"{filename}.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            return {"url": url, "status": "success", "file": filename}
        except httpx.HTTPStatusError as e:
            logging.error(f"HTTP error for {url}: {e.response.status_code}")
            return {
                "url": url,
                "status": "http_error",
                "status_code": e.response.status_code,
                "error": str(e)
            }
        except httpx.TimeoutException as e:
            logging.error(f"Timeout for {url}")
            return {"url": url, "status": "timeout", "error": str(e)}
        except Exception as e:
            logging.error(f"Error fetching {url}: {str(e)}")
            return {"url": url, "status": "error", "error": str(e)}


async def fetch_all_urls(urls_data, max_concurrent=5):
    """
    Fetches all URLs concurrently and logs the results.

    Args:
        urls_data (list): A list of dictionaries containing URL data.
        max_concurrent (int): The maximum number of concurrent requests.

    Returns:
        None
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    # Define HTTP client limits and headers
    limits = httpx.Limits(
        max_keepalive_connections=5,
        max_connections=max_concurrent * 2,
        keepalive_expiry=10
    )
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    # Create an HTTP client with specified limits and headers
    async with httpx.AsyncClient(timeout=10, limits=limits, headers=headers) as client:
        tasks = [fetch_and_save(client, url_data, semaphore) for url_data in urls_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Get current UTC date and hour
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H")
    
    # Save fetch results with timestamp in the filename
    log_filename = logs_dir / f"fetch_logs_{timestamp}.json"
    with open(log_filename, "w") as f:
        json.dump(results, f)


if __name__ == "__main__":
    # List of JSON files containing URL data
    json_files = [
        "bytedance_seed.json",
        "anthropic.json",
    ]

    urls_data = []
    for j in json_files:
        file_path = script_dir / 'schemas' / j
        with open(file_path, 'r') as f:
            data = json.load(f)
            base_url = data.get('site')
            domain = re.sub(r'[^\w]', '_', base_url.split('//')[-1].split('/')[0])
            pages = data.get('pages', [])
            for page in pages:
                urls_data.append({
                    'base_url': base_url,
                    'domain': domain,
                    'page': page
                })
    
    # Run the fetch_all_urls function to fetch and save HTMLs
    asyncio.run(fetch_all_urls(urls_data, max_concurrent=5))