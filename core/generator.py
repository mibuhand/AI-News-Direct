import json
import os
from pathlib import Path
from datetime import datetime, timezone
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import glob
from aggregator import aggregate_all_organizations, ORGANIZATION_CONFIGS

# Directory containing the parsed JSON files
project_dir = Path(__file__).resolve().parent.parent
parsed_dir = project_dir / 'data' / 'parsed'
feeds_dir = project_dir / 'feeds'

# Ensure feeds directory exists
feeds_dir.mkdir(exist_ok=True)

def get_feed_icon(feed_name, source):
    """Get appropriate icon URL for the feed"""
    # First check if this is an aggregated feed and get icon from config
    if '_aggregated' in feed_name:
        org_key = feed_name.replace('_aggregated', '')
        if org_key in ORGANIZATION_CONFIGS:
            config = ORGANIZATION_CONFIGS[org_key]
            return config.get('icon_url', 'https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/icon.png')
    
    # Organization-specific icons (using public favicon URLs)
    if 'anthropic' in feed_name:
        return 'https://www.anthropic.com/favicon.ico'
    elif 'openai' in feed_name:
        return 'https://openai.com/favicon.ico'
    elif 'deepmind' in feed_name:
        return 'https://deepmind.google/static/icons/google_deepmind_32dp.c67bb05568f4.ico'
    elif 'google' in feed_name:
        return 'https://www.google.com/favicon.ico'
    elif 'bytedance' in feed_name:
        return 'https://lf3-static.bytednsdoc.com/obj/eden-cn/lapzild-tss/ljhwZthlaukjlkulzlp/favicon_1/favicon.ico'
    elif 'microsoft' in feed_name:
        return 'https://www.microsoft.com/favicon.ico'
    elif 'meta' in feed_name or 'facebook' in feed_name:
        return 'https://about.meta.com/favicon.ico'
    elif 'huggingface' in feed_name:
        return 'https://huggingface.co/favicon.ico'
    else:
        # Default AI News Direct icon
        return 'https://upload.wikimedia.org/wikipedia/en/4/43/Feed-icon.svg'


def create_atom_feed(entries, feed_title, feed_id, feed_link, base_url, feed_name='', source=''):
    """Create an Atom feed XML from entries using standardized schema"""
    # Create root feed element
    feed = Element('feed')
    feed.set('xmlns', 'http://www.w3.org/2005/Atom')
    
    # Feed metadata
    title = SubElement(feed, 'title')
    title.text = feed_title
    
    feed_id_elem = SubElement(feed, 'id')
    feed_id_elem.text = feed_id
    
    # Add main channel link (for favicon detection)
    main_link = SubElement(feed, 'link')
    main_link.set('href', base_url)
    
    # Add feed icon
    icon_url = get_feed_icon(feed_name, source)
    icon = SubElement(feed, 'icon')
    icon.text = icon_url
    
    # Add logo (same as icon for now)
    logo = SubElement(feed, 'logo')
    logo.text = icon_url
    
    updated = SubElement(feed, 'updated')
    updated.text = datetime.now(timezone.utc).isoformat()
    
    author = SubElement(feed, 'author')
    name = SubElement(author, 'name')
    name.text = 'AI News Direct'
    
    # Add entries
    for entry_data in entries:
        entry = SubElement(feed, 'entry')
        
        entry_title = SubElement(entry, 'title')
        entry_title.text = entry_data.get('title', 'No Title')
        
        entry_id = SubElement(entry, 'id')
        entry_id.text = entry_data.get('id', entry_data.get('url', f"urn:uuid:{hash(str(entry_data))}"))
        
        entry_link = SubElement(entry, 'link')
        entry_link.set('href', entry_data.get('url', ''))
        
        # Add external link if available
        if entry_data.get('external_url'):
            external_link = SubElement(entry, 'link')
            external_link.set('href', entry_data['external_url'])
            external_link.set('rel', 'related')
        
        entry_updated = SubElement(entry, 'updated')
        # Use published_date from standardized schema
        date_str = entry_data.get('published_date', '')
        if date_str:
            try:
                # Parse ISO format date
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                entry_updated.text = dt.isoformat()
            except (ValueError, TypeError):
                entry_updated.text = datetime.now(timezone.utc).isoformat()
        else:
            entry_updated.text = datetime.now(timezone.utc).isoformat()
        
        # Add categories
        categories = entry_data.get('categories', [])
        for category in categories:
            if category:  # Only add non-empty categories
                cat_elem = SubElement(entry, 'category')
                cat_elem.set('term', category)
        
        # Add summary/content
        summary = SubElement(entry, 'summary')
        summary_text = []
        
        # Add description if available
        description = entry_data.get('description', '')
        if description:
            summary_text.append(description)
        
        # Add organization info
        organization = entry_data.get('organization', '')
        if organization:
            summary_text.append(f"Organization: {organization}")
        
        # Add source and type info
        source = entry_data.get('source', '')
        entry_type = entry_data.get('type', '')
        if source and entry_type:
            source_display = source.replace('_', ' ').title()
            summary_text.append(f"Source: {source_display} ({entry_type})")
        
        # Add metadata action if available
        metadata = entry_data.get('metadata', {})
        if metadata.get('action'):
            summary_text.append(f"Action: {metadata['action']}")
        
        # Add objects info
        objects = entry_data.get('objects', [])
        if objects:
            objects_info = []
            for obj in objects:
                obj_str = obj.get('title', '')
                obj_type = obj.get('type', '')
                if obj_type:
                    obj_str += f" ({obj_type})"
                if obj_str:
                    objects_info.append(obj_str)
            if objects_info:
                summary_text.append(f"Related: {', '.join(objects_info)}")
        
        # Use description as fallback
        if not summary_text:
            summary_text = [entry_data.get('title', 'No Description')]
        
        summary.text = ' | '.join(summary_text)
    
    return feed

def generate_feeds():
    """Generate Atom feeds for all JSON files using standardized schema"""
    # First, create aggregated feeds for all organizations
    print("Creating aggregated organization feeds...")
    aggregate_all_organizations()
    
    json_files = glob.glob(str(parsed_dir / "*.json"))
    
    for json_file in json_files:
        filename = os.path.basename(json_file)
        feed_name = filename.replace('.json', '')
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not data:
                continue
            
            # Determine feed metadata from standardized schema
            first_entry = data[0] if data else {}
            source = first_entry.get('source', '')
            entry_type = first_entry.get('type', '')
            
            # Create feed metadata based on source and type
            if source == 'anthropic':
                if entry_type == 'news':
                    feed_title = 'Anthropic News'
                elif entry_type == 'research':
                    feed_title = 'Anthropic Research'
                elif entry_type == 'engineering':
                    feed_title = 'Anthropic Engineering'
                else:
                    feed_title = 'Anthropic Updates'
                base_url = 'https://www.anthropic.com'
            elif source == 'huggingface':
                feed_title = 'Hugging Face Activities'
                base_url = 'https://huggingface.co'
            elif source == 'bytedance_seed':
                if entry_type == 'blog':
                    feed_title = 'ByteDance Seed Blog'
                elif entry_type == 'research':
                    feed_title = 'ByteDance Seed Research'
                else:
                    feed_title = 'ByteDance Seed Updates'
                base_url = 'https://seed.bytedance.com'
            elif source.endswith('_aggregated'):
                org_key = source.replace('_aggregated', '')
                if org_key in ORGANIZATION_CONFIGS:
                    config = ORGANIZATION_CONFIGS[org_key]
                    feed_title = config['feed_title']
                    base_url = config['base_url']
                else:
                    feed_title = f'{org_key.title()} - All Activities'
                    base_url = 'https://example.com'
            else:
                # Fallback to filename-based logic
                if 'anthropic' in feed_name:
                    feed_title = f'Anthropic {entry_type.title()}'
                    base_url = 'https://www.anthropic.com'
                elif 'huggingface' in feed_name:
                    feed_title = 'Hugging Face Activities'
                    base_url = 'https://huggingface.co'
                elif any(org_key in feed_name for org_key in ORGANIZATION_CONFIGS.keys()):
                    # Find matching organization
                    for org_key, config in ORGANIZATION_CONFIGS.items():
                        if org_key in feed_name:
                            if 'aggregated' in feed_name:
                                feed_title = config['feed_title']
                            else:
                                feed_title = f'{config["name"]} {entry_type.title()}'
                            base_url = config['base_url']
                            break
                else:
                    feed_title = f'AI News - {feed_name.title()}'
                    base_url = 'https://example.com'
            
            feed_id = f"tag:ai-news-direct.local,2025:{feed_name}"
            feed_link = f"{base_url}/feed/{feed_name}.xml"
            
            # Create Atom feed
            feed_xml = create_atom_feed(data, feed_title, feed_id, feed_link, base_url, feed_name, source)
            
            # Pretty print XML
            rough_string = tostring(feed_xml, 'utf-8')
            reparsed = minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent="  ", encoding='utf-8')
            
            # Save to file
            output_file = feeds_dir / f"{feed_name}.xml"
            with open(output_file, 'wb') as f:
                f.write(pretty_xml)
            
            print(f"Generated: {output_file} ({len(data)} entries)")
            
        except Exception as e:
            print(f"Error processing {json_file}: {e}")

if __name__ == "__main__":
    generate_feeds()