import json
from bs4 import BeautifulSoup
import os
from pathlib import Path
import logging
from datetime import datetime, timezone
import hashlib
import re

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

    # Find DeepSeek configuration
    for site in sites_config:
        if site.get('organization_key') == 'deepseek':
            return {
                'output_files': site.get('output_files', {}),
                'cache_files': site.get('cache_files', {})
            }

    raise ValueError("DeepSeek configuration not found in sites_config.json")

def load_html(filename):
    """Load HTML content from cache file"""
    file_path = html_dir / filename
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return None
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return None

    soup = BeautifulSoup(html_content, 'html.parser')
    return soup

def extract_news_links(soup):
    """Extract all news article links from the main page"""
    base_url = "https://api-docs.deepseek.com"
    news_links = []

    # Find all links that match the news pattern
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '/zh-cn/news/' in href and href.startswith('/zh-cn/news/'):
            full_url = base_url + href
            title = link.get_text(strip=True)

            # Filter out the category header "新闻" and only include actual article links
            # Must contain "news" in href and have a meaningful title (not just "新闻")
            if title and 'news' in href and title != "新闻" and len(title) > 3:
                news_links.append({
                    'url': full_url,
                    'path': href,
                    'title': title
                })

    # Remove duplicates based on URL
    seen_urls = set()
    unique_links = []
    for link in news_links:
        if link['url'] not in seen_urls:
            seen_urls.add(link['url'])
            unique_links.append(link)

    logging.info(f"Found {len(unique_links)} unique news articles")
    return unique_links

def parse_date_from_url(url_path):
    """Parse date from URL path like /zh-cn/news/news250922"""
    # Extract the date code (e.g., "250922" from "news250922")
    match = re.search(r'/news/news(\d+)', url_path)
    if not match:
        return None

    date_code = match.group(1)

    # Handle different date formats
    if len(date_code) == 6:  # YYMMDD format like "250922"
        try:
            if date_code.startswith('2'):  # 20xx years
                year = 2000 + int(date_code[:2])
            else:  # 19xx years (unlikely but just in case)
                year = 1900 + int(date_code[:2])
            month = int(date_code[2:4])
            day = int(date_code[4:6])
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            pass
    elif len(date_code) == 4:  # MMDD format like "1226"
        try:
            # Assume current year if only month/day provided
            current_year = datetime.now().year
            month = int(date_code[:2])
            day = int(date_code[2:4])
            return datetime(current_year, month, day, tzinfo=timezone.utc)
        except ValueError:
            pass

    return None

def parse_date_from_title(title):
    """Parse date from title like 'DeepSeek V3.1 更新 2025/09/22'"""
    # Look for date pattern YYYY/MM/DD
    match = re.search(r'(\d{4})/(\d{1,2})/(\d{1,2})', title)
    if match:
        try:
            year = int(match.group(1))
            month = int(match.group(2))
            day = int(match.group(3))
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            pass

    return None

def create_article_from_link(news_item):
    """Create article data structure from news link info"""
    title = news_item['title']

    # Parse published date
    published_date = parse_date_from_title(title) or parse_date_from_url(news_item['path'])
    if not published_date:
        published_date = datetime.now(timezone.utc)

    # Generate unique ID
    id_components = [
        "deepseek",
        title,
        news_item['url'],
        published_date.isoformat()
    ]
    item_id = hashlib.md5("_".join(filter(None, id_components)).encode()).hexdigest()

    # Extract categories from title
    categories = []
    if 'V3.1' in title:
        categories.append('Model Update')
    elif 'V3' in title:
        categories.append('Model Release')
    elif 'R1' in title:
        categories.append('Reasoning Model')
    elif 'APP' in title:
        categories.append('Application')
    elif 'API' in title:
        categories.append('API Update')

    # Create description from title
    description = f"DeepSeek news: {title}"

    return {
        'id': item_id,
        'source': 'deepseek',
        'type': 'news',
        'title': title,
        'description': description,
        'url': news_item['url'],
        'published_date': published_date.isoformat(),
        'categories': categories,
        'organization': 'DeepSeek',
        'metadata': {
            'language': 'zh-cn',
            'url_path': news_item['path']
        },
        'objects': []
    }

def parse_deepseek_html(soup):
    """Parse the main DeepSeek page to extract news articles"""
    if not soup:
        logging.error("No soup provided")
        return []

    # Extract all news links
    news_links = extract_news_links(soup)
    if not news_links:
        logging.error("No news articles found")
        return []

    # Create article data for each news link
    articles = []
    for news_item in news_links:
        article = create_article_from_link(news_item)
        articles.append(article)

    # Remove duplicates using JSON string deduplication
    dedup_list = [json.loads(entry) for entry in list({json.dumps(d) for d in articles})]

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

    logging.info(f"Successfully parsed {len(dedup_list)} unique articles")
    return dedup_list

def save_to_json(articles, filename):
    """Save articles to JSON file"""
    try:
        config = load_config()
        output_files = config['output_files']

        # Determine the output filename based on the cache filename
        if 'main' in filename:
            page_type = 'main'
        else:
            page_type = 'main'  # default

        output_filename = output_files.get(page_type, 'deepseek_news.json')
        json_path = parsed_dir / output_filename

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(articles, f, indent=4, ensure_ascii=False)
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
            logging.info(f"Processing DeepSeek {page_type} file: {cache_filename}")
            soup = load_html(cache_filename)
            articles = parse_deepseek_html(soup)
            if articles:
                save_to_json(articles, cache_filename)
            else:
                logging.error("No articles to save")
        else:
            logging.error(f"Required cache file not found: {cache_filename}")