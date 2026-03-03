import json
from bs4 import BeautifulSoup
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
    
    # Find AIBase configuration
    for site in sites_config:
        if site.get('organization_key') == 'aibase':
            return {
                'output_files': site.get('output_files', {}),
                'cache_files': site.get('cache_files', {})
            }
    
    raise ValueError("AIBase configuration not found in sites_config.json")

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

def parse_relative_time(time_str):
    """Parse relative time strings like '8 小时前' or '2 天前' into ISO format"""
    if not time_str:
        return None
    
    time_str = time_str.strip()
    
    # Handle "X 小时前" (X hours ago)
    hours_match = re.search(r'(\d+)\s*小时前', time_str)
    if hours_match:
        hours = int(hours_match.group(1))
        dt = datetime.now(timezone.utc) - timedelta(hours=hours)
        return dt.isoformat()
    
    # Handle "X 天前" (X days ago)
    days_match = re.search(r'(\d+)\s*天前', time_str)
    if days_match:
        days = int(days_match.group(1))
        dt = datetime.now(timezone.utc) - timedelta(days=days)
        return dt.isoformat()
    
    # Handle date format like "02-13"
    short_date_match = re.match(r'(\d{2})-(\d{2})', time_str)
    if short_date_match:
        month = int(short_date_match.group(1))
        day = int(short_date_match.group(2))
        year = datetime.now().year
        try:
            dt = datetime(year, month, day, tzinfo=timezone.utc)
            return dt.isoformat()
        except ValueError:
            pass
    
    # Try standard date format YYYY-MM-DD HH:MM:SS
    try:
        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        return dt.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        pass
    
    return None

def extract_daily_news_from_html(soup):
    """Extract AI daily news from HTML structure"""
    articles = []
    
    # Find all news item links - they have href like /zh/daily/25844
    news_links = soup.find_all('a', href=re.compile(r'/zh/daily/\d+'))
    
    for link in news_links:
        try:
            # Extract URL and oid
            href = link.get('href', '')
            oid_match = re.search(r'/zh/daily/(\d+)', href)
            oid = oid_match.group(1) if oid_match else ''
            url = f"https://news.aibase.com{href}" if href.startswith('/') else href
            
            # Find the title - it's in a div with font600 and mainColor classes
            title_div = link.find('div', class_=lambda x: x and 'font600' in x and 'mainColor' in x)
            if not title_div:
                # Try alternative selector
                title_div = link.find('div', class_=re.compile(r'font600.*truncate2|truncate2.*font600'))
            
            if not title_div:
                continue
                
            title = title_div.get_text(strip=True)
            if not title:
                continue
            
            # Extract description - it's in a div with tipColor and truncate2 classes
            description = ''
            desc_div = link.find('div', class_=lambda x: x and 'tipColor' in x and 'truncate2' in x)
            if desc_div:
                description = desc_div.get_text(strip=True)
            
            # Clean up description - remove the boilerplate text
            cleaned_description = description
            if "欢迎来到【AI日报】栏目!" in cleaned_description:
                # Find where the actual content starts after the boilerplate
                parts = cleaned_description.split("新鲜AI产品点击了解：https://app.aibase.com/zh")
                if len(parts) > 1:
                    cleaned_description = parts[1].strip()
            
            # Extract date/time info - the date is in a div containing an icon-rili <i> element
            published_date = None
            # Find the icon element
            date_icon = link.find('i', class_=lambda x: x and 'icon-rili' in str(x))
            if date_icon:
                # Get the parent div and extract text
                date_div = date_icon.find_parent('div')
                if date_div:
                    # Get text content, excluding the icon element
                    date_text = date_div.get_text(strip=True)
                    published_date = parse_relative_time(date_text)
            
            # Extract page views - the view count is in a div containing an icon-fangwenliang1 <i> element
            pv = 0
            pv_icon = link.find('i', class_=lambda x: x and 'icon-fangwenliang1' in str(x))
            if pv_icon:
                pv_div = pv_icon.find_parent('div')
                if pv_div:
                    pv_text = pv_div.get_text(strip=True)
                    # Parse "11.5K" format
                    pv_match = re.search(r'([\d.]+)\s*K?', pv_text)
                    if pv_match:
                        pv_num = float(pv_match.group(1))
                        if 'K' in pv_text:
                            pv = int(pv_num * 1000)
                        else:
                            pv = int(pv_num)
            
            # Extract thumbnail image
            thumbnail = ''
            img = link.find('img', loading='lazy')
            if img:
                thumbnail = img.get('src', '')
            
            if not published_date:
                published_date = datetime.now(timezone.utc).isoformat()
            
            # Generate unique ID
            id_components = [
                "aibase",
                title,
                url,
                published_date
            ]
            item_id = hashlib.md5("_".join(filter(None, id_components)).encode()).hexdigest()
            
            article = {
                'id': item_id,
                'source': 'aibase',
                'type': 'daily_news',
                'title': title,
                'description': cleaned_description,
                'url': url,
                'published_date': published_date,
                'categories': ['AI Daily', '人工智能'],
                'organization': 'AIBase',
                'metadata': {
                    'thumbnail': thumbnail,
                    'page_views': pv,
                    'oid': oid
                },
                'objects': []
            }
            
            articles.append(article)
            logging.info(f"Extracted AIBase daily news: {title[:50]}...")
            
        except Exception as e:
            logging.warning(f"Failed to parse AIBase item: {e}")
            continue
    
    return articles

def parse_aibase_html(soup):
    """Parse the AIBase daily HTML to extract AI daily news"""
    if not soup:
        logging.error("No soup provided")
        return []
    
    # Extract news from HTML structure
    articles = extract_daily_news_from_html(soup)
    
    if not articles:
        logging.warning("No articles found in HTML structure")
        return []
    
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
    
    logging.info(f"Successfully parsed {len(dedup_list)} unique articles from AIBase daily")
    return dedup_list

def save_to_json(articles, filename):
    """Save articles to JSON file"""
    try:
        config = load_config()
        output_files = config['output_files']
        
        # Determine the output filename based on the cache filename
        if 'daily' in filename:
            page_type = 'daily'
        else:
            page_type = 'daily'
        
        output_filename = output_files.get(page_type, 'aibase_daily.json')
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
            logging.info(f"Processing AIBase {page_type} file: {cache_filename}")
            soup = load_html(cache_filename)
            if soup:
                articles = parse_aibase_html(soup)
                if articles:
                    save_to_json(articles, cache_filename)
                else:
                    logging.error("No articles to save")
            else:
                logging.error(f"Failed to load HTML from {cache_filename}")
        else:
            logging.error(f"Required cache file not found: {cache_filename}")
