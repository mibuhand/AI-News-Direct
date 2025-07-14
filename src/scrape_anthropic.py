import json
import asyncio
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

async def main():

    with open('schemas/anthropic.json', 'r') as file:
        schema = json.load(file)

    run_config = CrawlerRunConfig(
        scan_full_page=False,
        exclude_all_images=True,
        exclude_external_links=True,
        exclude_social_media_links=True,
        extraction_strategy=JsonCssExtractionStrategy(schema),
        cache_mode = CacheMode.BYPASS,
    )

    browser_config = BrowserConfig()  # Default browser configuration

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://www.anthropic.com/news",
            config=run_config
        )
        print(json.loads(result.extracted_content))

if __name__ == "__main__":
    asyncio.run(main())

