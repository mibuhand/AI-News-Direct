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

    # Find the container with research articles - they're not in the main grid but in a different container
    # Look for containers with multiple time elements and research links
    containers = soup.find_all('div', class_=lambda x: x and len(x) > 2)
    research_container = None

    for container in containers:
        links = container.find_all('a')
        times = container.find_all('time')
        if len(links) > 1 and len(times) > 1:  # Likely contains multiple research items
            research_container = container
            break

    if not research_container:
        logging.error("Research container not found")
        return post_items

    # Find all time elements, which indicate research articles
    time_elements = research_container.find_all('time')
    logging.info(f"Found {len(time_elements)} time elements in research container")

    for time_elem in time_elements:
        try:
            # Extract date
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

            # Find the parent container that holds the complete article info
            parent = time_elem.parent
            article_container = None
            level = 0

            while parent and level < 10:
                # Look for a container that has both a link and the time element
                link = parent.find('a')
                if link and (link.get('href', '').startswith('/research/') or link.get('href', '').startswith('/index/')):
                    article_container = parent
                    break
                parent = parent.parent
                level += 1

            if not article_container:
                logging.warning(f"Could not find article container for time element: {date_str}")
                continue

            # Extract the article link
            article_link = article_container.find('a')
            if not article_link:
                continue

            url = base_url + article_link.get('href', '')

            # Extract title and description from the link content
            full_text = article_link.get_text(strip=True)

            # Split the text into potential title and description
            # Look for different text segments within the link
            text_divs = article_link.find_all('div')
            text_segments = []

            for div in text_divs:
                div_text = div.get_text(strip=True)
                if div_text and len(div_text) > 5 and div_text.lower() not in ['publication', 'research', 'safety', 'product', 'release']:
                    text_segments.append(div_text)

            # Clean up and separate title from description
            title = ""
            description = ""

            if text_segments:
                # Find the shortest text that's likely the title (usually comes first and is shorter)
                title_candidates = [seg for seg in text_segments if len(seg) < 100]
                desc_candidates = [seg for seg in text_segments if len(seg) >= 100]

                if title_candidates:
                    title = title_candidates[0]  # Take the first short segment as title

                    # For description, try to find a longer segment that's different from title
                    if desc_candidates:
                        for desc in desc_candidates:
                            if not desc.startswith(title):  # Different from title
                                description = desc
                                break

                    # If no good description found, try extracting from full text
                    if not description and full_text and len(full_text) > len(title) + 10:
                        remaining_text = full_text
                        if remaining_text.startswith(title):
                            remaining_text = remaining_text[len(title):].strip()

                        # Take a reasonable portion as description
                        if len(remaining_text) > 20:
                            description = remaining_text[:300]  # Limit description length

                else:
                    # Fallback: use the full text but try to split it
                    if full_text:
                        # Try to find a reasonable break point
                        words = full_text.split()
                        if len(words) > 10:
                            # Take first part as title, rest as description
                            title_words = words[:8]  # First 8 words for title
                            title = ' '.join(title_words)
                            description = ' '.join(words[8:])
                        else:
                            title = full_text

            # Fallback if no title found
            if not title and full_text:
                title = full_text[:80]  # Take first 80 chars as title

            if not title:
                logging.warning(f"Could not extract title for URL: {url}")
                continue

            # Clean up description
            if description and description == title:
                description = ""  # Avoid duplicate title/description

            # Extract post type from sibling elements near the time
            post_type = ""
            if time_elem.parent:
                siblings = time_elem.parent.find_all(['div'], recursive=False)
                for sib in siblings:
                    sib_text = sib.get_text(strip=True).lower()
                    if sib_text in ['publication', 'research', 'safety', 'product', 'release', 'blog']:
                        post_type = sib_text.title()
                        break

            if not post_type:
                post_type = "Research"  # Default type

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
            logging.info(f"Extracted: {title[:50]}...")

        except Exception as e:
            logging.error(f"Error processing time element: {e}")
            continue

    logging.info(f"Successfully extracted {len(post_items)} items")
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