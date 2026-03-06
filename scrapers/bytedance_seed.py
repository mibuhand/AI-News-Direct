import json
from bs4 import BeautifulSoup
import os
from pathlib import Path
import logging
from datetime import datetime, timezone
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Directory containing the HTML files
project_dir = Path(__file__).resolve().parent.parent
html_dir = project_dir / 'data' / 'html_cache'
parsed_dir = project_dir / 'data' / 'parsed'
config_dir = project_dir / 'config'
# Ensure parsed directory exists
parsed_dir.mkdir(exist_ok=True)

def load_config():
    """Load site configuration to get output filenames and cache filenames"""
    config_file = config_dir / 'sites_config.json'
    with open(config_file, 'r', encoding='utf-8') as f:
        sites_config = json.load(f)
    
    # Find ByteDance configuration
    for site in sites_config:
        if site.get('organization_key') == 'bytedance':
            return {
                'output_files': site.get('output_files', {}),
                'cache_files': site.get('cache_files', {})
            }
    
    raise ValueError("ByteDance configuration not found in sites_config.json")

def extract_script_data(file_path):
    # Read the HTML file
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return None
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return None

    # Parse the HTML content
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the script tag containing window._ROUTER_DATA
    script_tag = soup.find('script', string=lambda text: 'window._ROUTER_DATA' in text)
    
    if not script_tag:
        logging.error("Script tag with window._ROUTER_DATA not found")
        return None

    # Extract the JSON string from the script content
    script_content = script_tag.get_text().strip()
    json_start_index = script_content.find('{')
    json_string = script_content[json_start_index:]

    try:
        # Load the JSON data
        router_data = json.loads(json_string)
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        return None

    return router_data


def parse_and_save(router_data):
    if not router_data or 'loaderData' not in router_data:
        logging.error("Invalid router data")
        return

    base_url = "https://seed.bytedance.com/"
    config = load_config()
    output_files = config['output_files']

    # Determine page type
    # Note: public_papers in URL maps to 'research' output type
    if any('blog' in ky for ky in router_data['loaderData'].keys()):
        page_type = 'blog'
    elif any('public_papers' in ky for ky in router_data['loaderData'].keys()):
        page_type = 'public_papers'
    else:
        logging.error("Unknown page type")
        return

    article_list = []
    
    # Handle different key patterns: blog uses '/page', public_papers uses '/layout'
    if page_type == 'blog':
        loader_data_key = '(locale$)/blog/page'
    elif page_type == 'public_papers':
        loader_data_key = '(locale$)/public_papers/layout'
    else:
        logging.error(f"Unsupported page type: {page_type}")
        return

    if loader_data_key not in router_data['loaderData']:
        logging.error(f"Loader data key {loader_data_key} not found")
        return

    for article in router_data['loaderData'][loader_data_key]['article_list']:
        # Extract basic data
        title_en = article['ArticleSubContentEn'].get('Title', '')
        title_zh = article['ArticleSubContentZh'].get('Title', '') if 'ArticleSubContentZh' in article else ''
        
        # Determine URL path based on page type (public_papers uses 'public_papers' in URL)
        url_path = 'public_papers' if page_type == 'public_papers' else page_type
        url_en = base_url + f'en/{url_path}/' + article['ArticleSubContentEn'].get('TitleKey', '')
        url_zh = base_url + f'zh/{url_path}/' + article['ArticleSubContentZh'].get('TitleKey', '') if 'ArticleSubContentZh' in article else ''
        abstract_en = article['ArticleSubContentEn'].get('Abstract', '')
        abstract_zh = article['ArticleSubContentZh'].get('Abstract', '') if 'ArticleSubContentZh' in article else ''
        
        # Parse publish date to ISO format
        publish_date = article['ArticleMeta'].get('PublishDate')
        
        # Generate unique ID using high-cardinality fields (skip low-cardinality page_type)
        id_components = [
            "bytedance_seed",
            title_en,
            url_en,
            str(publish_date) if publish_date else '',
            hashlib.md5(abstract_en.encode()).hexdigest()[:8] if abstract_en else ''  # content hash for uniqueness
        ]
        item_id = hashlib.md5("_".join(filter(None, id_components)).encode()).hexdigest()
        if publish_date:
            published_date = datetime.fromtimestamp(publish_date / 1000).replace(tzinfo=timezone.utc).isoformat()
        else:
            published_date = datetime.now(timezone.utc).isoformat()
        
        # Extract categories
        categories = [area.get('ResearchAreaName', '') for area in article['ArticleMeta'].get('ResearchArea', [])]
        
        # Prepare metadata
        metadata = {}
        # public_papers contains research-type content with author, journal, etc.
        if page_type == 'public_papers':
            metadata['author'] = article['ArticleMeta'].get('Author', '')
            metadata['journal'] = article['ArticleMeta'].get('Journal', '')
            metadata['work_team'] = [team.get('Name', '') for team in article['ArticleMeta'].get('WorkingTeam', [])]
        
        # External URL
        external_url = ''
        if page_type == 'public_papers':
            external_links = article['ArticleMeta'].get('ExternalLinks', [])
            external_url = external_links[0].get('Link', '') if external_links else ''
        
        # Determine output type: public_papers maps to 'research' for consistency
        output_type = 'research' if page_type == 'public_papers' else page_type
        
        # Create standardized article data
        article_data = {
            'id': item_id,
            'source': 'bytedance_seed',
            'type': output_type,
            'title': title_en,
            'description': abstract_en,
            'url': url_en,
            'published_date': published_date,
            'categories': categories,
            'organization': 'ByteDance Seed',
            'metadata': metadata,
            'objects': []
        }
        
        # Add localized content if available
        if title_zh or abstract_zh or url_zh:
            article_data['title_localized'] = {'en': title_en, 'zh': title_zh}
            article_data['description_localized'] = {'en': abstract_en, 'zh': abstract_zh}
            article_data['url_localized'] = {'en': url_en, 'zh': url_zh}
        
        # Add external URL if available
        if external_url:
            article_data['external_url'] = external_url

        article_list.append(article_data)

    # Remove duplicates using JSON string deduplication
    dedup_list = [json.loads(entry) for entry in list({json.dumps(d) for d in article_list})]
    
    # Sort by published_date in reverse chronological order (newest first)
    def get_date_for_sorting(item):
        date_str = item.get('published_date', '')
        if date_str:
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                pass
        return datetime.min.replace(tzinfo=timezone.utc)
    
    dedup_list.sort(key=get_date_for_sorting, reverse=True)

    # Dump as json file using config-driven filename
    # Map public_papers to research key in config
    config_key = 'research' if page_type == 'public_papers' else page_type
    try:
        filename = output_files.get(config_key, f'bytedance_seed_{config_key}.json')
        json_path = parsed_dir / filename
        with open(json_path, 'w') as f:
            json.dump(dedup_list, f, indent=4)
            logging.info(f"Parsed data successfully written to '{json_path}'")
    except IOError as e:
        logging.error(f"Error writing to file: {e}")


if __name__ == "__main__":
    config = load_config()
    cache_files = config['cache_files']
    
    # Process each configured cache file
    for page_type, cache_filename in cache_files.items():
        file_path = html_dir / cache_filename
        if file_path.exists():
            logging.info(f"Processing ByteDance {page_type} file: {cache_filename}")
            router_data = extract_script_data(file_path)
            parse_and_save(router_data)
        else:
            logging.error(f"Required cache file not found: {cache_filename}")