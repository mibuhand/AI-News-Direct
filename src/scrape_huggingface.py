import json
import asyncio
from itertools import product
import os
from pathlib import Path
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

async def scrape_huggingface(json_path):

    with open(json_path, 'r') as file:
        info = json.load(file)

    base_url = info['base_url']

    # Organization Activities
    orgs = info['schemas']['organizations']['org_list'][25:26]
    org_base_url = info['schemas']['organizations']['url']
    pages = info['schemas']['organizations']['pages']
    org_schema = info['schemas']['organizations']['schema']
    org_urls = [base_url+org_base_url+z[0]+z[1] for z in list(product(orgs, pages))]

    run_config = CrawlerRunConfig(
        scan_full_page=False,
        exclude_all_images=True,
        exclude_external_links=True,
        exclude_social_media_links=True,
        extraction_strategy=JsonCssExtractionStrategy(org_schema),
        cache_mode = CacheMode.BYPASS,
    )

    browser_config = BrowserConfig()  # Default browser configuration

    async with AsyncWebCrawler(config=browser_config) as crawler:
        results = await crawler.arun_many(
            urls=org_urls,
            config=run_config
        )
        
    return results

def post_process(results):
    for result in results:
        print(result.extracted_content)
        print()


if __name__ == "__main__":
    script_dir = Path(__file__).resolve().parent
    json_dir = os.path.join(script_dir, 'schemas', 'huggingface.json')
    results = asyncio.run(scrape_huggingface(json_dir))
    post_process(results)

