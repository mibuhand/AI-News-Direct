import json
import os
from pathlib import Path
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import glob

# Directory paths
project_dir = Path(__file__).resolve().parent.parent
parsed_dir = project_dir / 'data' / 'parsed'
feeds_dir = project_dir / 'feeds'
config_dir = project_dir / 'config'

# Ensure feeds directory exists
feeds_dir.mkdir(exist_ok=True)

def load_sites_config():
    """Load sites configuration from JSON file"""
    config_file = config_dir / 'sites_config.json'
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading sites config: {e}")
        return []

SITES_CONFIG = load_sites_config()

def get_favicon_url(feed_name):
    """Get favicon URL for feed based on name matching with sites config"""
    for site_config in SITES_CONFIG:
        org_key = site_config.get('organization_key', '')
        if org_key and org_key in feed_name.lower():
            return site_config.get('favicon_url', '')
    return 'https://upload.wikimedia.org/wikipedia/en/4/43/Feed-icon.svg'

def get_base_url(feed_name):
    """Get base URL for feed based on name matching with sites config"""
    for site_config in SITES_CONFIG:
        org_key = site_config.get('organization_key', '')
        if org_key and org_key in feed_name.lower():
            return site_config.get('site', 'https://example.com')
    return 'https://ai-news-direct.local'

def safe_get_text(data, key, fallback=''):
    """Safely get text value from data, handling None and non-string types"""
    value = data.get(key, fallback)
    if value is None:
        return fallback
    return str(value).strip()

def format_date(date_str):
    """Format date string to ISO format, with fallback to current time"""
    if not date_str:
        return datetime.now(timezone.utc).isoformat()
    
    try:
        # Handle various date formats
        if 'T' in str(date_str):
            # ISO format
            dt = datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
        else:
            # Assume it's a simple date, add time
            dt = datetime.fromisoformat(f"{date_str}T00:00:00+00:00")
        return dt.isoformat()
    except (ValueError, TypeError):
        return datetime.now(timezone.utc).isoformat()

def create_atom_feed(entries, feed_name):
    """Create an Atom feed from entries with whatever data is available"""
    # Create root feed element
    feed = Element('feed')
    feed.set('xmlns', 'http://www.w3.org/2005/Atom')
    
    # Feed metadata
    title = SubElement(feed, 'title')
    title.text = feed_name.replace('_', ' ').title()
    
    feed_id_elem = SubElement(feed, 'id')
    feed_id_elem.text = f"tag:ai-news-direct.local,2025:{feed_name}"
    
    # Add feed icon
    icon_url = get_favicon_url(feed_name)
    if icon_url:
        icon = SubElement(feed, 'icon')
        icon.text = icon_url
        
        logo = SubElement(feed, 'logo')
        logo.text = icon_url
    
    # Feed updated time
    updated = SubElement(feed, 'updated')
    updated.text = datetime.now(timezone.utc).isoformat()
    
    # Author
    author = SubElement(feed, 'author')
    name = SubElement(author, 'name')
    name.text = 'AI News Direct'
    
    # Link to feed (GitHub raw URL)
    link = SubElement(feed, 'link')
    link.set('href', f"https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/{feed_name}.xml")
    link.set('rel', 'self')
    
    # Process each entry
    for entry_data in entries:
        if not isinstance(entry_data, dict):
            continue
            
        entry = SubElement(feed, 'entry')
        
        # Entry title
        entry_title = SubElement(entry, 'title')
        title_text = safe_get_text(entry_data, 'title', 'Untitled')
        entry_title.text = title_text
        
        # Entry ID
        entry_id = SubElement(entry, 'id')
        id_text = safe_get_text(entry_data, 'id', safe_get_text(entry_data, 'url', f"urn:feed:{feed_name}:{hash(str(entry_data))}"))
        entry_id.text = id_text
        
        # Entry link
        url = safe_get_text(entry_data, 'url')
        if url:
            entry_link = SubElement(entry, 'link')
            entry_link.set('href', url)
        
        # External URL if different from main URL
        external_url = safe_get_text(entry_data, 'external_url')
        if external_url and external_url != url:
            external_link = SubElement(entry, 'link')
            external_link.set('href', external_url)
            external_link.set('rel', 'replies')
            external_link.set('title', 'Discussion')
        
        # Entry updated/published date
        entry_updated = SubElement(entry, 'updated')
        date_str = safe_get_text(entry_data, 'published_date', safe_get_text(entry_data, 'date'))
        entry_updated.text = format_date(date_str)
        
        # Categories (if available)
        categories = entry_data.get('categories', [])
        if isinstance(categories, list):
            for category in categories:
                if category and str(category).strip():
                    cat_elem = SubElement(entry, 'category')
                    cat_elem.set('term', str(category).strip())
        
        # Content/Summary - only include meaningful content, not metadata
        content_parts = []
        
        # Description (main content)
        description = safe_get_text(entry_data, 'description')
        if description:
            content_parts.append(description)
        
        # Objects/Related items (actual content)
        objects = entry_data.get('objects', [])
        if isinstance(objects, list) and objects:
            related_items = []
            for obj in objects:
                if isinstance(obj, dict):
                    obj_title = safe_get_text(obj, 'title', safe_get_text(obj, 'obj_title'))
                    obj_type = safe_get_text(obj, 'type', safe_get_text(obj, 'obj_type'))
                    obj_url = safe_get_text(obj, 'url', safe_get_text(obj, 'obj_url'))
                    
                    if obj_title:
                        item_text = obj_title
                        if obj_type:
                            item_text += f" ({obj_type})"
                        if obj_url:
                            item_text += f" - {obj_url}"
                        related_items.append(item_text)
            
            if related_items:
                content_parts.append(f"Related: {'; '.join(related_items)}")
        
        # Any other meaningful content fields (exclude metadata/technical fields)
        excluded_fields = {
            'title', 'id', 'url', 'external_url', 'published_date', 'date', 
            'categories', 'description', 'organization', 'source', 'type', 
            'metadata', 'objects'
        }
        
        for key, value in entry_data.items():
            if key not in excluded_fields and value:
                if isinstance(value, (str, int, float)) and str(value).strip():
                    # Only include if it looks like actual content, not technical metadata
                    value_str = str(value).strip()
                    if len(value_str) > 10:  # Only include substantial content
                        content_parts.append(f"{key.replace('_', ' ').title()}: {value_str}")
        
        # Create summary - only if we have actual content
        summary = SubElement(entry, 'summary')
        
        # For Hacker News entries, add discussion link info
        source = entry_data.get('source', '')
        if source == 'hackernews' and external_url and external_url != url:
            metadata = entry_data.get('metadata', {})
            score = metadata.get('score', 0)
            comments = metadata.get('comments', 0)
            author = metadata.get('author', '')
            
            hn_info = f"Score: {score}"
            if comments > 0:
                hn_info += f" | Comments: {comments}"
            if author:
                hn_info += f" | By: {author}"
            hn_info += f" | Discussion: {external_url}"
            
            if content_parts:
                summary.text = " | ".join(content_parts) + " | " + hn_info
            else:
                summary.text = hn_info
        elif content_parts:
            summary.text = " | ".join(content_parts)
        else:
            # No summary if there's no meaningful content beyond title
            summary.text = ""
    
    return feed

def generate_feeds():
    """Generate Atom feeds for all JSON files in the parsed directory"""
    json_files = glob.glob(str(parsed_dir / "*.json"))
    
    if not json_files:
        print("No JSON files found in data/parsed/ directory")
        return
    
    print(f"Found {len(json_files)} JSON files to process...")
    
    for json_file in json_files:
        filename = os.path.basename(json_file)
        feed_name = filename.replace('.json', '')
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not data:
                print(f"Skipping {filename} - no data")
                continue
            
            if not isinstance(data, list):
                print(f"Skipping {filename} - data is not a list")
                continue
            
            print(f"Processing {filename} with {len(data)} entries...")
            
            # Create Atom feed
            feed_xml = create_atom_feed(data, feed_name)
            
            # Pretty print XML
            rough_string = tostring(feed_xml, 'utf-8')
            reparsed = minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent="  ", encoding='utf-8')
            
            # Save to file
            output_file = feeds_dir / f"{feed_name}.xml"
            with open(output_file, 'wb') as f:
                f.write(pretty_xml)
            
            print(f"Generated: {output_file}")
            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")

if __name__ == "__main__":
    generate_feeds()