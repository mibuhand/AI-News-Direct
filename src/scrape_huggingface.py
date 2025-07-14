import json
import os
from pprint import pprint
from itertools import product
from pathlib import Path
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
import asyncio
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy


async def scrape_huggingface(json_path):

    with open(json_path, 'r') as file:
        info = json.load(file)

    base_url = info['base_url']

    # Organization Activities
    orgs = info['schemas']['organizations']['org_list'][26:27]
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
    

def post_process_huggingface(results):
    base_url = 'https://huggingface.co'
    utc_now = datetime.now(timezone.utc)
    cnt = 0
    activity_list = []
    for result_raw in results:
        result = json.loads(result_raw.extracted_content)
        for act in result:
            activity = {}
            activity['organization'] = result_raw.url.removeprefix(base_url).split('/')[2]
            # activity['author'] = [act['author'].removeprefix('/')]
            # activity['author_url'] = base_url + act['author']
            action_str = act['action'] + ' ' + act['target'].removeprefix(act['action'])
            activity['action'] = ' '.join(action_str.split()).strip()

            activity['objects'] = []
            for obj in act['objects']:
                obj_out = {}
                obj_out['url'] = base_url + obj['obj_url']
                obj_out['title'] = ' '.join(obj['obj_title'].split()).strip()
                if 'model' in act['target']:
                    obj_out['model_type'] = obj['obj_info'].split('•')[0]
                activity['objects'].append(obj_out)

            time_ago = int(''.join([char for char in act['date'] if char.isdigit()]))
            if 'hour' in act['date'] or 'minute' in act['date']:
                activity['date'] = utc_now.strftime('%Y-%m-%d')
            elif 'day' in act['date']:
                act_time = utc_now - relativedelta(days=time_ago)
                activity['date'] = act_time.strftime('%Y-%m-%d')
            elif 'month' in act['date']:
                act_time = utc_now - relativedelta(months=time_ago)
                activity['date'] = act_time.strftime('%Y-%m')
            elif 'year' in act['date']:
                act_time = utc_now - relativedelta(years=time_ago)
                activity['date'] = act_time.strftime('%Y')

            activity_list.append(activity)
            cnt += 1

    dedup_list = [json.loads(entry) for entry in list({json.dumps(d) for d in activity_list})]
    return dedup_list




if __name__ == "__main__":
    script_dir = Path(__file__).resolve().parent
    json_dir = os.path.join(script_dir, 'schemas', 'huggingface.json')
    results = asyncio.run(scrape_huggingface(json_dir))
    post_process_huggingface(results)

