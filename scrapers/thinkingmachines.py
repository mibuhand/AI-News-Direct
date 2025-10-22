import json
from bs4 import BeautifulSoup
import os
from pathlib import Path
import logging
from datetime import datetime, timezone, timedelta
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

    # Find Thinking Machines configuration
    for site in sites_config:
        if site.get('organization_key') == 'thinkingmachines':
            return {
                'output_files': site.get('output_files', {}),
                'cache_files': site.get('cache_files', {})
            }

    raise ValueError("Thinking Machines configuration not found in sites_config.json")

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

def parse_date(date_text):
    """Parse date from blog post date text like 'Oct 1' or 'Sep 29'"""
    if not date_text:
        return datetime.now(timezone.utc)

    try:
        # Handle formats like "Oct 1", "Sep 29"
        current_date = datetime.now(timezone.utc)
        current_year = current_date.year

        # Try current year first
        date_with_year = f"{date_text} {current_year}"
        parsed_date = datetime.strptime(date_with_year, "%b %d %Y")
        parsed_date = parsed_date.replace(tzinfo=timezone.utc)

        # If the parsed date is more than 2 months in the future, assume it's from the previous year
        future_threshold = current_date + timedelta(days=60)  # ~2 months
        if parsed_date > future_threshold:
            parsed_date = parsed_date.replace(year=current_year - 1)

        # If the parsed date is more than 18 months in the past, assume it's from the next year
        # (unlikely but handles edge cases around year boundaries)
        past_threshold = current_date - timedelta(days=545)  # ~18 months
        if parsed_date < past_threshold:
            parsed_date = parsed_date.replace(year=current_year + 1)

        return parsed_date
    except ValueError:
        logging.warning(f"Could not parse date: {date_text}")
        return datetime.now(timezone.utc)

def extract_blog_posts(soup):
    """Extract blog posts from the Thinking Machines blog page"""
    base_url = "https://thinkingmachines.ai"
    posts = []

    # Look for blog post links with the specific class "post-item-link"
    blog_links = soup.find_all('a', class_='post-item-link')

    for link in blog_links:
        href = link.get('href')
        if not href or href == '/blog/':
            continue

        # Extract title from the div with class "post-title"
        title_div = link.find('div', class_='post-title')
        title = title_div.get_text(strip=True) if title_div else None

        # Extract date from the time element with class "desktop-time"
        date_time = link.find('time', class_='desktop-time')
        date_text = date_time.get_text(strip=True) if date_time else None

        # Extract author from the span with class "author"
        author_span = link.find('span', class_='author')
        author_text = author_span.get_text(strip=True) if author_span else None

        # Skip if we don't have a meaningful title
        if not title or len(title) < 3:
            continue

        full_url = base_url + href if href.startswith('/') else href

        posts.append({
            'title': title,
            'url': full_url,
            'path': href,
            'date_text': date_text,
            'author': author_text or 'Thinking Machines Lab'
        })

    # Remove duplicates based on URL
    seen_urls = set()
    unique_posts = []
    for post in posts:
        if post['url'] not in seen_urls:
            seen_urls.add(post['url'])
            unique_posts.append(post)

    logging.info(f"Found {len(unique_posts)} unique blog posts")
    return unique_posts

def create_article_from_post(post):
    """Create article data structure from blog post info"""
    title = post['title']

    # Parse published date
    published_date = parse_date(post['date_text'])

    # Generate unique ID
    id_components = [
        "thinkingmachines",
        title,
        post['url'],
        published_date.isoformat()
    ]
    item_id = hashlib.md5("_".join(filter(None, id_components)).encode()).hexdigest()

    # Extract categories from title
    categories = []
    title_lower = title.lower()
    if 'lora' in title_lower or 'fine-tuning' in title_lower:
        categories.append('Fine-tuning')
    elif 'llm' in title_lower or 'language model' in title_lower:
        categories.append('Language Models')
    elif 'inference' in title_lower:
        categories.append('Inference')
    elif 'manifold' in title_lower:
        categories.append('Theory')
    elif 'tinker' in title_lower:
        categories.append('Tools')
    else:
        categories.append('Research')

    # Create description
    description = f"{title}"
    if post['author'] and post['author'] != 'Thinking Machines Lab' and post['author'].strip():
        description += f" by {post['author']}"

    return {
        'id': item_id,
        'source': 'thinkingmachines',
        'type': 'blog',
        'title': title,
        'description': description,
        'url': post['url'],
        'published_date': published_date.isoformat(),
        'categories': categories,
        'organization': 'Thinking Machines Lab',
        'metadata': {
            'author': post['author'],
            'url_path': post['path'],
            'date_text': post['date_text']
        },
        'objects': []
    }

def parse_thinkingmachines_html(soup):
    """Parse the Thinking Machines blog page to extract blog posts"""
    if not soup:
        logging.error("No soup provided")
        return []

    # Extract all blog posts
    blog_posts = extract_blog_posts(soup)
    if not blog_posts:
        logging.error("No blog posts found")
        return []

    # Create article data for each blog post
    articles = []
    for post in blog_posts:
        article = create_article_from_post(post)
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
        if 'blog' in filename:
            page_type = 'blog'
        else:
            page_type = 'blog'  # default

        output_filename = output_files.get(page_type, 'thinkingmachines_blog.json')
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
            logging.info(f"Processing Thinking Machines {page_type} file: {cache_filename}")
            soup = load_html(cache_filename)
            articles = parse_thinkingmachines_html(soup)
            if articles:
                save_to_json(articles, cache_filename)
            else:
                logging.error("No articles to save")
        else:
            logging.error(f"Required cache file not found: {cache_filename}")