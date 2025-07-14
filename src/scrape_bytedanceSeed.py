import json
import re
from datetime import datetime, timedelta
import asyncio
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy, RegexExtractionStrategy

PAGE_URL = "https://seed.bytedance.com"

async def main():

    run_config = CrawlerRunConfig(
        scan_full_page=False,
        exclude_all_images=True,
        exclude_external_links=True,
        exclude_social_media_links=True,
        cache_mode = CacheMode.BYPASS,
    )

    browser_config = BrowserConfig()  # Default browser configuration

    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url=PAGE_URL + '/blog',
            config=run_config
        )

    match = re.search(
        r"window\._ROUTER_DATA\s*=\s*(.*?)(?:;\s*)?</script>",
        result.html,
        re.DOTALL
    )

    if match:
        data = json.loads(match.group(1).strip())
        for article in data['loaderData']['(locale$)/blog/page']['article_list']:
            title_en = article['ArticleSubContentEn']['Title']
            title_zh = article['ArticleSubContentZh']['Title']
            publish_date = datetime.fromtimestamp(article['ArticleMeta']['PublishDate']/1000)
            researchArea_en = [area['ResearchAreaName'] for area in article['ArticleMeta']['ResearchArea']]
            researchArea_zh = [area['ResearchAreaNameZh'] for area in article['ArticleMeta']['ResearchArea']]
            url_en = PAGE_URL + '/en/blog/' + article['ArticleSubContentEn']['TitleKey']
            url_zh = PAGE_URL + '/zh/blog/' + article['ArticleSubContentZh']['TitleKey']
            abstract_en = article['ArticleSubContentEn']['Abstract']
            abstract_zh = article['ArticleSubContentZh']['Abstract']
            print(title_en)
            print(title_zh)
            print(publish_date)
            print(researchArea_en)
            print(researchArea_zh)
            print(url_en)
            print(url_zh)
            print(abstract_en)
            print(abstract_zh)
            print()

if __name__ == "__main__":
    asyncio.run(main())
