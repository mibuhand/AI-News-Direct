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
    
    # Find Artificial Analysis configuration
    for site in sites_config:
        if site.get('organization_key') == 'artificial_analysis':
            return {
                'output_files': site.get('output_files', {}),
                'cache_files': site.get('cache_files', {})
            }
    
    raise ValueError("Artificial Analysis configuration not found in sites_config.json")

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
    
    # Try specific format (e.g., "March 5, 2026")
    try:
        dt = datetime.strptime(date_str, '%B %d, %Y')
        dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except ValueError:
        pass
    
    logging.warning(f"Could not parse date: '{date_str}'")
    return None

def extract_articles(soup):
    """Extract articles from the HTML"""
    articles = []
    
    # Find all article links with href starting with /articles/
    article_links = soup.find_all('a', href=re.compile(r'^/articles/'))
    
    logging.info(f"Found {len(article_links)} article links")
    
    for link in article_links:
        try:
            # Get the href (slug)
            href = link.get('href', '')
            slug = href.replace('/articles/', '')
            
            # Get the title from h2 element
            title_elem = link.find('h2')
            title = title_elem.get_text(strip=True) if title_elem else ''
            
            # Get the date from p element
            date_elem = link.find('p')
            date_str = date_elem.get_text(strip=True) if date_elem else ''
            
            # Get the image URL from the img element
            img_elem = link.find('img')
            image_url = img_elem.get('src', '') if img_elem else ''
            
            if not title:
                logging.warning(f"Skipping article without title: {href}")
                continue
            
            # Parse the date
            published_date = parse_date(date_str)
            if not published_date:
                published_date = datetime.now(timezone.utc).isoformat()
            
            # Generate URL
            url = f"https://artificialanalysis.ai{href}"
            
            # Generate unique ID
            id_components = [
                "artificial_analysis",
                title,
                url
            ]
            item_id = hashlib.md5("_".join(filter(None, id_components)).encode()).hexdigest()
            
            article = {
                'id': item_id,
                'source': 'artificial_analysis',
                'type': 'article',
                'title': title,
                'description': '',
                'url': url,
                'published_date': published_date,
                'categories': [],
                'organization': 'Artificial Analysis',
                'metadata': {
                    'image_url': image_url,
                    'slug': slug
                },
                'objects': []
            }
            articles.append(article)
            logging.info(f"Extracted article: {title[:50]}...")
            
        except Exception as e:
            logging.warning(f"Failed to parse article: {e}")
            continue
    
    return articles

def main():
    """Main function to run the scraper"""
    logging.info("Starting Artificial Analysis scraper...")
    
    # Load configuration
    config = load_config()
    output_filename = config['output_files'].get('articles', 'artificial_analysis.json')
    cache_filename = config['cache_files'].get('articles', 'artificial_analysis.html')
    
    logging.info(f"Output file: {output_filename}")
    logging.info(f"Cache file: {cache_filename}")
    
    # Load HTML
    soup = load_html(cache_filename)
    if not soup:
        logging.error("Failed to load HTML")
        return
    
    # Extract articles
    articles = extract_articles(soup)
    
    if not articles:
        logging.warning("No articles found")
        # Save empty array to maintain consistency
        articles = []
    
    # Sort articles by published_date descending
    articles.sort(key=lambda x: x.get('published_date', ''), reverse=True)
    
    # Save to JSON
    output_path = parsed_dir / output_filename
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(articles, f, indent=2, ensure_ascii=False)
    
    logging.info(f"Saved {len(articles)} articles to {output_path}")

if __name__ == '__main__':
    main()
