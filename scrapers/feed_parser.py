import json
import xml.etree.ElementTree as ET
from pathlib import Path
import logging
from datetime import datetime, timezone
import hashlib
from dateutil import parser as date_parser
import glob

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Directory containing the feed files
project_dir = Path(__file__).resolve().parent.parent
feeds_cache_dir = project_dir / 'data' / 'feeds_cache'
parsed_dir = project_dir / 'data' / 'parsed'
# Ensure parsed directory exists
parsed_dir.mkdir(exist_ok=True)


def parse_rss_feed(xml_content, source_name):
    """Parse RSS feed XML content into standardized format"""
    try:
        root = ET.fromstring(xml_content)
        items = []
        
        # Handle RSS format
        if root.tag == 'rss':
            channel = root.find('channel')
            if channel is not None:
                for item in channel.findall('item'):
                    parsed_item = parse_rss_item(item, source_name)
                    if parsed_item:
                        items.append(parsed_item)
        
        # Handle Atom format
        elif root.tag.endswith('feed'):
            for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
                parsed_item = parse_atom_entry(entry, source_name)
                if parsed_item:
                    items.append(parsed_item)
        
        return items
        
    except ET.ParseError as e:
        logging.error(f"XML parsing error for {source_name}: {e}")
        return []
    except Exception as e:
        logging.error(f"Error parsing feed {source_name}: {e}")
        return []


def parse_rss_item(item, source_name):
    """Parse individual RSS item"""
    try:
        title = get_text_content(item.find('title'))
        description = get_text_content(item.find('description'))
        link = get_text_content(item.find('link'))
        pub_date = get_text_content(item.find('pubDate'))
        guid = get_text_content(item.find('guid'))
        
        # Parse publication date
        published_date = parse_date(pub_date)
        
        # Extract categories
        categories = []
        for category in item.findall('category'):
            cat_text = get_text_content(category)
            if cat_text:
                categories.append(cat_text)
        
        # Generate unique ID
        id_components = [
            source_name,
            title or '',
            link or '',
            guid or '',
            published_date
        ]
        item_id = hashlib.md5("_".join(filter(None, id_components)).encode()).hexdigest()
        
        return {
            'id': item_id,
            'source': source_name,
            'type': 'news',
            'title': title or '',
            'description': description or '',
            'url': link or '',
            'published_date': published_date,
            'categories': categories,
            'organization': get_organization_name(source_name),
            'metadata': {
                'guid': guid or '',
                'feed_type': 'rss'
            },
            'objects': []
        }
        
    except Exception as e:
        logging.error(f"Error parsing RSS item: {e}")
        return None


def parse_atom_entry(entry, source_name):
    """Parse individual Atom entry"""
    try:
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        title = get_text_content(entry.find('atom:title', ns))
        summary = get_text_content(entry.find('atom:summary', ns))
        
        # Get link
        link_elem = entry.find('atom:link[@rel="alternate"]', ns)
        if link_elem is None:
            link_elem = entry.find('atom:link', ns)
        link = link_elem.get('href') if link_elem is not None else ''
        
        # Get dates
        published = get_text_content(entry.find('atom:published', ns))
        updated = get_text_content(entry.find('atom:updated', ns))
        pub_date = published or updated
        
        # Get ID
        entry_id = get_text_content(entry.find('atom:id', ns))
        
        # Parse publication date
        published_date = parse_date(pub_date)
        
        # Extract categories
        categories = []
        for category in entry.findall('atom:category', ns):
            term = category.get('term')
            if term:
                categories.append(term)
        
        # Generate unique ID
        id_components = [
            source_name,
            title or '',
            link or '',
            entry_id or '',
            published_date
        ]
        item_id = hashlib.md5("_".join(filter(None, id_components)).encode()).hexdigest()
        
        return {
            'id': item_id,
            'source': source_name,
            'type': 'news',
            'title': title or '',
            'description': summary or '',
            'url': link or '',
            'published_date': published_date,
            'categories': categories,
            'organization': get_organization_name(source_name),
            'metadata': {
                'entry_id': entry_id or '',
                'feed_type': 'atom'
            },
            'objects': []
        }
        
    except Exception as e:
        logging.error(f"Error parsing Atom entry: {e}")
        return None


def get_text_content(element):
    """Safely extract text content from XML element"""
    if element is not None and element.text:
        return element.text.strip()
    return ''


def parse_date(date_string):
    """Parse various date formats to ISO format"""
    if not date_string:
        return datetime.now(timezone.utc).isoformat()
    
    try:
        # Use dateutil parser for flexible date parsing
        parsed_date = date_parser.parse(date_string)
        # Ensure timezone aware
        if parsed_date.tzinfo is None:
            parsed_date = parsed_date.replace(tzinfo=timezone.utc)
        return parsed_date.isoformat()
    except Exception:
        # Fallback to current time
        return datetime.now(timezone.utc).isoformat()


def load_organization_configs():
    """Load organization configurations from JSON file"""
    config_dir = project_dir / 'config'
    config_file = config_dir / 'organizations.json'
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading organization config: {e}")
        return {}

def get_organization_name(source_name):
    """Map source name to organization name using config file"""
    org_configs = load_organization_configs()
    
    source_lower = source_name.lower()
    
    # Check each organization's patterns
    for org_key, config in org_configs.items():
        for pattern in config.get('patterns', []):
            if pattern.lower() in source_lower:
                return config.get('name', org_key.title())
    
    # Fallback: check if source_name matches org key directly
    if source_lower in org_configs:
        return org_configs[source_lower].get('name', source_name.title())
    
    return source_name.title()


def process_all_feeds():
    """Process all XML feeds in the feeds_cache directory"""
    feed_files = glob.glob(str(feeds_cache_dir / "*.xml"))
    
    if not feed_files:
        logging.warning("No XML feed files found in feeds_cache directory")
        return
    
    for feed_file in feed_files:
        try:
            filename = Path(feed_file).stem
            source_name = extract_source_from_filename(filename)
            
            with open(feed_file, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            items = parse_rss_feed(xml_content, source_name)
            
            if items:
                save_parsed_feed(items, source_name)
                logging.info(f"Processed {len(items)} items from {filename}")
            else:
                logging.warning(f"No items found in {filename}")
                
        except Exception as e:
            logging.error(f"Error processing {feed_file}: {e}")


def extract_source_from_filename(filename):
    """Extract source name from filename"""
    # Remove common domain patterns and clean up
    source = filename.replace('_com_', '_').replace('_org_', '_')
    
    # Extract the main domain part
    parts = source.split('_')
    if len(parts) > 0:
        return parts[0]
    
    return filename


def get_source_org_from_config(source_name):
    """Get the organization key that matches the source name"""
    org_configs = load_organization_configs()
    
    source_lower = source_name.lower()
    
    # Check each organization's patterns
    for org_key, config in org_configs.items():
        for pattern in config.get('patterns', []):
            if pattern.lower() in source_lower:
                return org_key
    
    # Fallback: check if source_name matches org key directly
    if source_lower in org_configs:
        return source_lower
    
    return source_name


def save_parsed_feed(items, source_name):
    """Save parsed feed items to JSON file"""
    # Remove duplicates using JSON string deduplication
    dedup_list = [json.loads(entry) for entry in list({json.dumps(d) for d in items})]
    
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
    
    try:
        # Use organization key for consistent naming
        org_key = get_source_org_from_config(source_name)
        json_path = parsed_dir / f'{org_key}_feeds.json'
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(dedup_list, f, indent=4)
        logging.info(f"Saved {len(dedup_list)} items to {json_path}")
    except IOError as e:
        logging.error(f"Error writing to file: {e}")


if __name__ == "__main__":
    process_all_feeds()