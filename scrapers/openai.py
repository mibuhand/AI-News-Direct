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
    
    # Find OpenAI configuration for research pages
    for site in sites_config:
        if (site.get('organization_key') == 'openai' and 
            site.get('type') != 'feeds'):
            return {
                'output_files': site.get('output_files', {}),
                'cache_files': site.get('cache_files', {})
            }
    
    raise ValueError("OpenAI research configuration not found in sites_config.json")


def load_html(filename):
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

    # Parse the HTML content
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup


def extract_html_data(soup):
    base_url = 'https://openai.com'
    post_items = []
    
    # Find the grid container with articles
    grid_container = soup.find('div', class_='grid')
    if not grid_container:
        logging.error("Grid container not found")
        return post_items

    # Extract each article from the grid
    articles = grid_container.find_all('div', class_=lambda x: x and 'py-md' in x and 'border-primary-12' in x)
    
    for article in articles:
        # Extract metadata section
        meta_section = article.find('div', class_='text-meta')
        if not meta_section:
            continue
            
        # Extract post type (Publication, Product, Safety, Release, etc.)
        type_elem = meta_section.find('div')
        post_type = type_elem.get_text(strip=True) if type_elem else ''
        
        # Extract date
        time_elem = meta_section.find('time')
        if not time_elem:
            continue
            
        date_str = time_elem.get('datetime', '')
        if not date_str:
            date_str = time_elem.get_text(strip=True)
            
        # Parse date to ISO format
        try:
            if 'T' in date_str:
                # Already in ISO format with time
                published_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).replace(tzinfo=timezone.utc).isoformat()
            else:
                # Date only format like "Jul 22, 2025"
                parsed_date = datetime.strptime(date_str, '%b %d, %Y').replace(tzinfo=timezone.utc)
                published_date = parsed_date.isoformat()
        except:
            # Fallback to current time if parsing fails
            published_date = datetime.now(timezone.utc).isoformat()
        
        # Extract article link and content
        article_link = article.find('a')
        if not article_link:
            continue
            
        url = base_url + article_link.get('href', '')
        
        # Extract title
        title_elem = article_link.find('div', class_='text-h5')
        if not title_elem:
            continue
            
        title = title_elem.get_text(strip=True)
        
        # Extract description
        desc_elem = article_link.find('p', class_='text-p2')
        description = desc_elem.get_text(strip=True) if desc_elem else ''
        
        # Generate unique ID using high-cardinality fields
        id_components = [
            "openai",
            title,
            url,
            published_date,
            post_type
        ]
        item_id = hashlib.md5("_".join(filter(None, id_components)).encode()).hexdigest()
        
        # Create standardized article data
        out_item = {
            'id': item_id,
            'source': 'openai',
            'type': post_type.lower(),
            'title': title,
            'description': description,
            'url': url,
            'published_date': published_date,
            'categories': [post_type] if post_type else [],
            'organization': 'OpenAI',
            'metadata': {
                'post_type': post_type
            },
            'objects': []
        }
        post_items.append(out_item)

    return post_items


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

    # Get config-driven filename
    config = load_config()
    output_files = config['output_files']
    output_filename = output_files.get('main', 'openai_research.json')
    
    try:
        json_path = parsed_dir / output_filename
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
            logging.info(f"Processing OpenAI {page_type} file: {cache_filename}")
            soup = load_html(cache_filename)
            if soup:
                post_items = extract_html_data(soup)
                save_to_json(post_items, cache_filename)
        else:
            logging.error(f"Required cache file not found: {cache_filename}")