import asyncio
from curl_cffi.requests import AsyncSession
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
html_cache_dir = project_dir / "data" / "html_cache"
logs_dir = project_dir / "data" / "logs"

# Ensure the cache and logs directories exist
html_cache_dir.mkdir(exist_ok=True)
logs_dir.mkdir(exist_ok=True)


async def fetch_and_save(curl_session, url_data, semaphore):
    """
    Fetches a URL and saves the HTML content to a file.

    Args:
        curl_session (AsyncSession): The curl_cffi session used for all requests.
        url_data (dict): A dictionary containing 'base_url', 'domain', 'page'.
        semaphore (asyncio.Semaphore): A semaphore to limit concurrent requests.

    Returns:
        dict: A dictionary with the URL, status, and file name or error details.
    """
    async with semaphore:
        # Construct the full URL
        url = urljoin(url_data['base_url'].rstrip('/')+'/', url_data['page'])
        
        try:
            try:
                response = await curl_session.get(url, impersonate="chrome120", timeout=10)
                response.raise_for_status()
                response_text = response.text
            except Exception as e:
                # Handle curl_cffi errors
                if hasattr(e, 'response') and hasattr(e.response, 'status_code'):  # type: ignore
                    status_code = e.response.status_code  # type: ignore
                    logging.error(f"HTTP {status_code} for {url}")
                    return {
                        "url": url,
                        "status": "http_error",
                        "status_code": status_code,
                        "error": f"HTTP {status_code}"
                    }
                elif 'timeout' in str(e).lower():
                    logging.error(f"Timeout for {url}")
                    return {"url": url, "status": "timeout", "error": str(e)}
                else:
                    logging.error(f"Error fetching {url}: {str(e)}")
                    return {"url": url, "status": "error", "error": str(e)}

            # Use domain and page from JSON data to construct filename
            domain = re.sub(r'[^\w]', '_', url_data['domain'])
            page = re.sub(r'[^\w]', '_', url_data['page'].replace('/', '_'))

            # Ensure the filename is in "domain_page" format
            if not page:
                page = 'index'  # Default to 'index' if no specific page path is provided

            # Use config-driven filename
            config_filename = url_data.get('cache_filename', '')
            if not config_filename:
                raise ValueError(f"No cache filename configured for URL: {url}")
            
            # Remove extension since we'll add .html
            filename = config_filename.replace('.html', '')

            # Save HTML content
            with open(html_cache_dir / f"{filename}.html", "w", encoding="utf-8") as f:
                f.write(response_text)
            return {"url": url, "status": "success", "file": filename, "type": "html"}
            
        except Exception as e:
            logging.error(f"Unexpected error fetching {url}: {str(e)}")
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

    # Create curl_cffi session
    async with AsyncSession() as curl_session:
        tasks = [fetch_and_save(curl_session, url_data, semaphore) for url_data in urls_data]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Get current UTC date and hour
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H")
    
    # Save fetch results with timestamp in the filename
    log_filename = logs_dir / f"fetch_logs_{timestamp}.json"
    with open(log_filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Track and log unsuccessful requests
    failed_requests = []
    successful_count = 0
    
    for result in results:
        if isinstance(result, dict) and result.get("status") != "success":
            failed_requests.append(result)
        elif isinstance(result, dict) and result.get("status") == "success":
            successful_count += 1
    
    # Log summary
    total_requests = len(results)
    logging.info(f"Fetch summary: {successful_count}/{total_requests} successful")
    
    if failed_requests:
        logging.info(f"Failed requests ({len(failed_requests)}):")
        for failed in failed_requests:
            url = failed.get("url", "Unknown URL")
            status = failed.get("status", "unknown")
            if status == "http_error":
                status_code = failed.get("status_code", "unknown")
                logging.info(f"  - {url} (HTTP {status_code})")
            else:
                logging.info(f"  - {url} ({status})")
    else:
        logging.info("All requests were successful!")


if __name__ == "__main__":
    # Load URL data from unified schema
    urls_data = []
    file_path = project_dir / 'config' / 'sites_config.json'
    
    with open(file_path, 'r', encoding="utf-8") as f:
        data_list = json.load(f)
        
        for data in data_list:
            base_url = data.get('site')
            domain = re.sub(r'[^\w]', '_', base_url.split('//')[-1].split('/')[0])
            client_type = data.get('client_type', 'curl_cffi')  # Default to curl_cffi
            organization_key = data.get('organization_key', '')
            
            # Skip Hacker News and Hugging Face as they use direct API calls
            if organization_key in ['hackernews', 'huggingface']:
                continue
            
            # Handle simple pages list
            pages = data.get('pages', [''])
            cache_files = data.get('cache_files', {})
            
            for page in pages:
                # Extract content type from page path
                content_type = page.strip('/').replace('/', '_') if page.strip('/') else 'main'
                
                # Get config-driven cache filename
                cache_filename = cache_files.get(content_type, '')
                
                urls_data.append({
                    'base_url': base_url,
                    'domain': domain,
                    'page': page,
                    'content_type': content_type,
                    'cache_filename': cache_filename,
                    'client_type': client_type
                })
    
    logging.info(f"Total URLs to fetch: {len(urls_data)}")
    
    # Run the fetch_all_urls function to fetch and save HTMLs
    asyncio.run(fetch_all_urls(urls_data, max_concurrent=5))