import json
from bs4 import BeautifulSoup
import os
from pathlib import Path
import logging
from datetime import datetime, timezone
import codecs
from dateutil import parser
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
    
    # Find Anthropic configuration
    for site in sites_config:
        if site.get('organization_key') == 'anthropic':
            return {
                'output_files': site.get('output_files', {}),
                'cache_files': site.get('cache_files', {})
            }
    
    raise ValueError("Anthropic configuration not found in sites_config.json")


def load_html(filename):
    file_path = html_dir / filename
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

    return soup




def _extract_research_data(soup, base_url):
    """Extract data from research pages using new CSS module selectors"""
    post_items = []
    
    # Process PublicationList items (research publications list)
    publication_items = soup.select('a[class*="PublicationList-module-scss-module"][class*="listItem"]')
    for post in publication_items:
        # Extract title from the title span
        title_element = post.select_one('[class*="PublicationList-module-scss-module"][class*="title"]')
        
        # Extract date from time element
        date_element = post.select_one('[class*="PublicationList-module-scss-module"][class*="date"]')
        
        # Extract category from subject span
        category_element = post.select_one('[class*="PublicationList-module-scss-module"][class*="subject"]')
        categories = [category_element.get_text(strip=True)] if category_element else []
        
        if title_element:
            post_item = _create_post_item(
                post, title_element, date_element, base_url, 'research', soup, categories
            )
            if post_item:
                post_items.append(post_item)
    
    # Also process FeaturedGrid items (featured research articles)
    featured_items = soup.select('a[class*="FeaturedGrid-module-scss-module"][class*="sideLink"]')
    for post in featured_items:
        # Title from headline element
        title_element = post.select_one('[class*="FeaturedGrid-module-scss-module"][class*="title"]')
        
        # Date from time element
        date_element = post.select_one('[class*="FeaturedGrid-module-scss-module"][class*="date"]')
        
        # Category from caption bold
        category_element = post.select_one('span.caption.bold')
        categories = [category_element.get_text(strip=True)] if category_element else []
        
        if title_element:
            post_item = _create_post_item(
                post, title_element, date_element, base_url, 'research', soup, categories
            )
            if post_item:
                post_items.append(post_item)
    
    return post_items


def _extract_news_data(soup, base_url):
    """Extract data from news pages using new CSS module selectors"""
    post_items = []
    
    # Process PublicationList items (main news list)
    publication_items = soup.select('a[class*="PublicationList-module-scss-module"][class*="listItem"]')
    for post in publication_items:
        # Extract title from the title span
        title_element = post.select_one('[class*="PublicationList-module-scss-module"][class*="title"]')
        
        # Extract date from time element
        date_element = post.select_one('[class*="PublicationList-module-scss-module"][class*="date"]')
        
        # Extract category from subject span
        category_element = post.select_one('[class*="PublicationList-module-scss-module"][class*="subject"]')
        categories = [category_element.get_text(strip=True)] if category_element else []
        
        if title_element:
            post_item = _create_post_item(
                post, title_element, date_element, base_url, 'news', soup, categories
            )
            if post_item:
                post_items.append(post_item)
    
    # Also try FeaturedGrid side items (featured/side articles)
    featured_items = soup.select('a[class*="FeaturedGrid-module-scss-module"][class*="sideLink"]')
    for post in featured_items:
        # Title from headline element
        title_element = post.select_one('[class*="FeaturedGrid-module-scss-module"][class*="title"]')
        
        # Date from time element
        date_element = post.select_one('[class*="FeaturedGrid-module-scss-module"][class*="date"]')
        
        # Category from caption bold
        category_element = post.select_one('span.caption.bold')
        categories = [category_element.get_text(strip=True)] if category_element else []
        
        if title_element:
            post_item = _create_post_item(
                post, title_element, date_element, base_url, 'news', soup, categories
            )
            if post_item:
                post_items.append(post_item)
    
    return post_items


def _extract_engineering_data(soup, base_url):
    """Extract data from engineering pages using new CSS module selectors"""
    post_items = []
    
    # Process ArticleList items (engineering blog articles)
    # The CSS module hash can vary, so we look for the article elements more broadly
    article_items = soup.find_all('article', class_=lambda x: x and 'ArticleList-module' in x)
    for post in article_items:
        # Find the card link within the article - look for any anchor with cardLink in class
        card_link = post.find('a', class_=lambda x: x and 'cardLink' in x)
        if not card_link:
            continue
            
        # Try h3.headline-4 first (regular articles), then h2.headline-1 (featured)
        title_element = post.select_one('h3.headline-4')
        if not title_element:
            title_element = post.select_one('h2.headline-1')
        
        # Date from the date div - look for class ending with '__date'
        # This is more specific to avoid matching other date-related classes
        date_element = post.find('div', class_=lambda x: x and '__date' in str(x))
        
        if title_element:
            post_item = _create_post_item(
                card_link, title_element, date_element, base_url, 'engineering', soup
            )
            if post_item:
                post_items.append(post_item)
    
    return post_items


def _create_post_item(post, title_element, date_element, base_url, page_type, soup, categories=None):
    """Create a post item from extracted elements"""
    title = title_element.get_text(strip=True) if title_element else ''
    if not title:
        return None
        
    url = str(base_url) + str(post['href'])
    
    # Handle date extraction with error handling
    published_date = None
    if date_element:
        date_str = date_element.get_text(strip=True)
        try:
            published_date = datetime.strptime(date_str, '%b %d, %Y').replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            logging.warning(f"Could not parse date '{date_str}' for article '{title[:50]}...'")
            published_date = None
    
    # Fallback to current date if parsing failed or no date element found
    if not published_date:
        published_date = datetime.now(timezone.utc).isoformat()
    
    # Generate unique ID using high-cardinality fields
    id_components = [
        "anthropic",
        title,
        url,
        published_date
    ]
    item_id = hashlib.md5("_".join(filter(None, id_components)).encode()).hexdigest()
    
    return {
        'id': item_id,
        'source': 'anthropic',
        'type': page_type,
        'title': title,
        'description': '',
        'url': url,
        'published_date': published_date,
        'categories': categories or [],
        'organization': 'Anthropic',
        'metadata': {},
        'objects': []
    }




def save_to_json(post_items, filename):
    # Remove duplicates using JSON string deduplication
    dedup_list = [json.loads(entry) for entry in list({json.dumps(d) for d in post_items})]
    
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

    # Determine page type and get config-driven filename
    config = load_config()
    output_files = config['output_files']
    if 'news' in filename:
        page_type = 'news'
    elif 'engineering' in filename:
        page_type = 'engineering'
    elif 'research' in filename:
        page_type = 'research'

    try:
        output_filename = output_files.get(page_type, f'anthropic_{page_type}.json')
        json_path = parsed_dir / output_filename
        with open(json_path, 'w') as f:
            json.dump(dedup_list, f, indent=4)
            logging.info(f"Parsed data successfully written to '{json_path}'")
    except IOError as e:
        logging.error(f"Error writing to file: {e}")


def extract_html_data(soup, filename):
    """Route to the appropriate extraction function based on filename"""
    if 'research' in filename:
        return _extract_research_data(soup, 'https://www.anthropic.com/research/')
    elif 'engineering' in filename:
        return _extract_engineering_data(soup, 'https://www.anthropic.com/engineering/')
    elif 'news' in filename:
        return _extract_news_data(soup, 'https://www.anthropic.com/news/')
    else:
        logging.error(f"Unknown file type: {filename}")
        return []


if __name__ == "__main__":
    config = load_config()
    cache_files = config['cache_files']
    
    # Process each configured cache file
    for page_type, cache_filename in cache_files.items():
        file_path = html_dir / cache_filename
        if file_path.exists():
            logging.info(f"Processing Anthropic {page_type} file: {cache_filename}")
            soup = load_html(cache_filename)
            if soup:
                post_items = extract_html_data(soup, cache_filename)
                save_to_json(post_items, cache_filename)
            else:
                logging.error(f"Failed to load HTML from {cache_filename}")
        else:
            logging.error(f"Required cache file not found: {cache_filename}")