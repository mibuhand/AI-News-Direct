import json
from bs4 import BeautifulSoup
from pathlib import Path
import logging
from datetime import datetime, timezone
import hashlib
import re
from dateutil import parser as date_parser

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
    
    # Find DeepLearning AI configuration
    for site in sites_config:
        if site.get('organization_key') == 'deeplearning_ai':
            return {
                'output_files': site.get('output_files', {}),
                'cache_files': site.get('cache_files', {})
            }
    
    raise ValueError("DeepLearning AI configuration not found in sites_config.json")

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

def parse_date(date_str):
    """Parse date string to ISO format"""
    if not date_str:
        return None
    
    # Clean up the date string
    date_str = date_str.strip()
    
    try:
        # Try parsing with dateutil which handles various formats
        dt = date_parser.parse(date_str)
        # Ensure timezone info is present
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except (ValueError, TypeError):
        pass
    
    # Try specific format for the batch dates (ISO format with timezone)
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.isoformat()
    except ValueError:
        pass
    
    logging.warning(f"Could not parse date: '{date_str}'")
    return None

def extract_date_from_tag(tags):
    """Extract date from tags list"""
    if not tags:
        return None
    
    for tag in tags:
        tag_name = tag.get('name', '')
        # Check if tag looks like a date (e.g., "Mar 06, 2026" or "February 27, 2026")
        if re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}$', tag_name, re.IGNORECASE):
            return parse_date(tag_name)
    
    return None

def extract_posts(soup):
    """Extract posts from the Next.js data"""
    posts = []
    
    # Find the __NEXT_DATA__ script
    next_data_script = soup.find('script', id='__NEXT_DATA__')
    if not next_data_script:
        logging.error("Could not find __NEXT_DATA__ script")
        return posts
    
    try:
        data = json.loads(next_data_script.string)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON: {e}")
        return posts
    
    # Navigate to the posts
    try:
        page_props = data.get('props', {}).get('pageProps', {})
        posts_data = page_props.get('posts', [])
    except (KeyError, TypeError) as e:
        logging.error(f"Failed to navigate to posts: {e}")
        return posts
    
    for post_data in posts_data:
        try:
            title = post_data.get('title', '')
            slug = post_data.get('slug', '')
            feature_image = post_data.get('feature_image', '')
            custom_excerpt = post_data.get('custom_excerpt', '')
            published_at = post_data.get('published_at', '')
            tags = post_data.get('tags', [])
            
            # Parse the date
            published_date = parse_date(published_at)
            if not published_date:
                # Try to extract from tags
                published_date = extract_date_from_tag(tags)
            
            if not published_date:
                published_date = datetime.now(timezone.utc).isoformat()
            
            # Generate URL
            url = f"https://www.deeplearning.ai/the-batch/{slug}/"
            
            # Generate unique ID (without datetime as per requirement)
            id_components = [
                "deeplearning_ai",
                title,
                url
            ]
            item_id = hashlib.md5("_".join(filter(None, id_components)).encode()).hexdigest()
            
            # Extract category from tags
            categories = []
            for tag in tags:
                tag_name = tag.get('name', '')
                # Skip date tags and issue tags
                if tag_name and not re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}$', tag_name, re.IGNORECASE):
                    if not tag_name.startswith('issue-'):
                        categories.append(tag_name)
            
            post = {
                'id': item_id,
                'source': 'deeplearning_ai',
                'type': 'newsletter',
                'title': title,
                'description': custom_excerpt,
                'url': url,
                'published_date': published_date,
                'categories': categories,
                'organization': 'DeepLearning.AI',
                'metadata': {
                    'feature_image': feature_image,
                    'tags': [tag.get('name', '') for tag in tags]
                },
                'objects': []
            }
            posts.append(post)
            logging.info(f"Extracted post: {title[:50]}...")
            
        except Exception as e:
            logging.warning(f"Failed to parse post: {e}")
            continue
    
    return posts

def main():
    """Main function to run the scraper"""
    logging.info("Starting DeepLearning AI The Batch scraper...")
    
    # Load configuration
    config = load_config()
    output_filename = config['output_files'].get('main', 'deeplearning_ai_batch.json')
    cache_filename = config['cache_files'].get('main', 'deeplearning_ai_batch.html')
    
    logging.info(f"Output file: {output_filename}")
    logging.info(f"Cache file: {cache_filename}")
    
    # Load HTML
    soup = load_html(cache_filename)
    if not soup:
        logging.error("Failed to load HTML")
        return
    
    # Extract posts
    posts = extract_posts(soup)
    
    if not posts:
        logging.warning("No posts found")
        # Save empty array to maintain consistency
        posts = []
    
    # Sort posts by published_date descending
    posts.sort(key=lambda x: x.get('published_date', ''), reverse=True)
    
    # Save to JSON
    output_path = parsed_dir / output_filename
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(posts, f, indent=2, ensure_ascii=False)
    
    logging.info(f"Saved {len(posts)} posts to {output_path}")

if __name__ == '__main__':
    main()
