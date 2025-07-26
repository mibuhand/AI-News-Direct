import json
import os
import re
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
import logging
import glob
import hashlib

# Configure logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')

# Directory containing the HTML files
project_dir = Path(__file__).resolve().parent.parent
html_dir = project_dir / 'data' / 'html_cache'
parsed_dir = project_dir / 'data' / 'parsed'

# Ensure parsed directory exists
parsed_dir.mkdir(exist_ok=True)

# Hardcoded CSS selectors (simplified from huggingface.json schema)
BASE_SELECTOR = "div.org-profile-content div.mb-7"
USER_BASE_SELECTOR = "div.user-profile-content div.mb-7"
ACTION_SELECTOR = ".mb-3 .text-smd .flex.items-baseline span span"
TARGET_SELECTOR = ".mb-3 .text-smd .flex.items-baseline span"
DATE_SELECTOR = ".ml-4"
OBJECTS_SELECTOR = "div.space-y-3 article.overview-card-wrapper"
OBJECT_URL_SELECTOR = "a"
OBJECT_TITLE_SELECTOR = "h4"
OBJECT_INFO_SELECTOR = "div.mr-1"


def load_huggingface_html_files():
    """Load HTML files from data/html_cache and extract data using hardcoded selectors"""
    base_url = 'https://huggingface.co'
    
    # Find all HTML files with 'huggingface' in filename
    html_files = glob.glob(str(html_dir / "*huggingface*"))
    all_activities = []
    
    for html_file in html_files:
        try:
            filename = os.path.basename(html_file)
            
            with open(html_file, 'r', encoding='utf-8') as file:
                html_content = file.read()
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract organization name from filename
            org_name = extract_org_from_filename(filename)
            
            # Extract activities using hardcoded selectors
            activities = extract_activities_from_html(soup, org_name)
            all_activities.extend(activities)
            
            # Only log if no activities found (special case)
            if len(activities) == 0:
                logging.warning(f"No activities extracted from {filename} (org: {org_name})")
            
        except Exception as e:
            logging.error(f"Error processing {html_file}: {e}")
    
    # Only log if no activities found at all (special case)
    if len(all_activities) == 0:
        logging.warning(f"No activities found in any of {len(html_files)} HTML files")
    
    return all_activities


def extract_org_from_filename(filename):
    """Extract organization name from HTML filename"""
    # Remove .html extension
    name_without_ext = filename.replace('.html', '')
    
    # Handle different filename patterns
    if 'huggingface_co_' in name_without_ext:
        # Pattern: huggingface_co__Kijai_activity_models.html or huggingface_co__organizations_Kijai_activity_datasets.html
        parts = name_without_ext.split('huggingface_co_')[1]
        
        # Remove leading underscores
        while parts.startswith('_'):
            parts = parts[1:]
        
        # Handle organizations pattern: huggingface_co__organizations_Kijai_activity_datasets.html
        if parts.startswith('organizations_'):
            parts = parts.replace('organizations_', '')
        
        # Extract organization name (first part before underscore or activity)
        if '_activity_' in parts:
            org_name = parts.split('_activity_')[0]
        elif '_' in parts:
            # For patterns like "Kijai_activity_models", take the first part
            org_name = parts.split('_')[0]
        else:
            org_name = parts
            
    elif 'organizations_' in name_without_ext:
        # Pattern: organizations_openai.html
        org_name = name_without_ext.replace('organizations_', '')
    else:
        # Fallback: use the whole filename without extension
        org_name = name_without_ext
    
    return org_name


def extract_activities_from_html(soup, org_name):
    """Extract activities using hardcoded CSS selectors"""
    activities = []
    
    # Try multiple selector patterns to find activity items
    activity_items = []
    
    # First try the main selector
    activity_items = soup.select(BASE_SELECTOR)
    
    # If no items found, try user profile selector
    if not activity_items:
        activity_items = soup.select(USER_BASE_SELECTOR)
    
    for item in activity_items:
        activity = {'organization': org_name}
        
        # Extract action
        action_elem = item.select_one(ACTION_SELECTOR)
        activity['action'] = action_elem.get_text(strip=True) if action_elem else ''
        
        # Extract target
        target_elem = item.select_one(TARGET_SELECTOR)
        activity['target'] = target_elem.get_text(strip=True) if target_elem else ''
        
        # Extract date
        date_elem = item.select_one(DATE_SELECTOR)
        activity['date'] = date_elem.get_text(strip=True) if date_elem else ''
        
        # Extract objects
        activity['objects'] = []
        object_items = item.select(OBJECTS_SELECTOR)
        
        for obj_item in object_items:
            obj_data = {}
            
            # Extract object URL
            obj_link = obj_item.select_one(OBJECT_URL_SELECTOR)
            if obj_link:
                obj_data['obj_url'] = obj_link.get('href', '')
            
            # Extract object title
            obj_title = obj_item.select_one(OBJECT_TITLE_SELECTOR)
            if obj_title:
                obj_data['obj_title'] = obj_title.get_text(strip=True)
            
            # Extract object info
            obj_info = obj_item.select_one(OBJECT_INFO_SELECTOR)
            if obj_info:
                obj_data['obj_info'] = obj_info.get_text(strip=True)
            
            if obj_data.get('obj_url') or obj_data.get('obj_title'):
                activity['objects'].append(obj_data)
        
        # If no structured data found, try to extract from text content
        if not activity['action'] and not activity['target'] and not activity['objects']:
            text_content = item.get_text(strip=True)
            if text_content and len(text_content) > 10:  # Only if there's meaningful content
                # Try to find links for objects
                links = item.select('a')
                for link in links:
                    href = link.get('href', '')
                    title = link.get_text(strip=True)
                    if href and title:
                        activity['objects'].append({
                            'obj_url': href,
                            'obj_title': title,
                            'obj_info': ''
                        })
                
                # Use text as action if no specific action found
                if not activity['action']:
                    activity['action'] = text_content[:100]  # Limit length
        
        # Only add activity if we found some meaningful content
        if activity['action'] or activity['target'] or activity['objects']:
            activities.append(activity)
    
    return activities


def post_process_huggingface(activities):
    """Process the extracted activities directly"""
    base_url = 'https://huggingface.co'
    utc_now = datetime.now(timezone.utc)
    activity_list = []

    for act in activities:
        organization = act.get('organization', '')
        
        # Process action and target
        action = act.get('action', '')
        target = act.get('target', '')
        action_str = f"{action} {target.removeprefix(action)}" if action and target else (action or target)
        action_clean = ' '.join(action_str.split()).strip()
        
        # Generate unique ID using high-cardinality fields
        id_components = [
            "huggingface",
            organization,
            action_clean,
            act.get('date', ''),
            str(len(act.get('objects', [])))  # number of objects adds uniqueness
        ]
        # Add first object URL/title if available for additional uniqueness
        if act.get('objects'):
            first_obj = act['objects'][0]
            if first_obj.get('obj_url'):
                id_components.append(first_obj['obj_url'])
            elif first_obj.get('obj_title'):
                id_components.append(first_obj['obj_title'])
        
        item_id = hashlib.md5("_".join(filter(None, id_components)).encode()).hexdigest()

        # Process objects
        objects = []
        for obj in act.get('objects', []):
            obj_url = obj.get('obj_url', '')
            obj_title = obj.get('obj_title', '')
            obj_info = obj.get('obj_info', '')
            
            if obj_url or obj_title:
                obj_out = {
                    'title': ' '.join(obj_title.split()).strip() if obj_title else '',
                    'url': f"{base_url}{obj_url}" if obj_url and not obj_url.startswith('http') else obj_url,
                    'type': ''
                }
                
                # Add model type if available
                if target and 'model' in target.lower() and obj_info:
                    if '•' in obj_info:
                        obj_out['type'] = obj_info.split('•')[0].strip()
                    else:
                        obj_out['type'] = obj_info.strip()
                
                objects.append(obj_out)

        # Process date with improved inference
        date_text = act.get('date', '')
        published_date = utc_now.isoformat()
        
        if date_text:
            date_text_lower = date_text.lower().strip()
            
            # Extract number and unit using regex parsing
            time_match = re.search(r'(\d+)\s*(minute|hour|day|week|month|year)', date_text_lower)
            
            if time_match:
                time_value = int(time_match.group(1))
                time_unit = time_match.group(2)
                
                if time_unit == 'minute':
                    act_time = utc_now - relativedelta(minutes=time_value)
                elif time_unit == 'hour':
                    act_time = utc_now - relativedelta(hours=time_value)
                elif time_unit == 'day':
                    act_time = utc_now - relativedelta(days=time_value)
                elif time_unit == 'week':
                    act_time = utc_now - relativedelta(weeks=time_value)
                elif time_unit == 'month':
                    act_time = utc_now - relativedelta(months=time_value)
                elif time_unit == 'year':
                    act_time = utc_now - relativedelta(years=time_value)
                else:
                    act_time = utc_now
                    
                published_date = act_time.isoformat()
            
            # Handle special cases like "yesterday", "today", etc.
            elif 'yesterday' in date_text_lower:
                act_time = utc_now - relativedelta(days=1)
                published_date = act_time.isoformat()
            elif 'today' in date_text_lower or 'now' in date_text_lower:
                published_date = utc_now.isoformat()
            
            # Fallback to original logic if no match
            elif any(unit in date_text_lower for unit in ['minute', 'hour', 'day', 'month', 'year']):
                time_numbers = ''.join([char for char in date_text if char.isdigit()])
                time_ago = int(time_numbers) if time_numbers else 1
                
                if 'minute' in date_text_lower:
                    act_time = utc_now - relativedelta(minutes=time_ago)
                elif 'hour' in date_text_lower:
                    act_time = utc_now - relativedelta(hours=time_ago)
                elif 'day' in date_text_lower:
                    act_time = utc_now - relativedelta(days=time_ago)
                elif 'month' in date_text_lower:
                    act_time = utc_now - relativedelta(months=time_ago)
                elif 'year' in date_text_lower:
                    act_time = utc_now - relativedelta(years=time_ago)
                else:
                    act_time = utc_now
                    
                published_date = act_time.isoformat()

        # Create standardized activity data
        activity = {
            'id': item_id,
            'source': 'huggingface',
            'type': 'activity',
            'title': f"[HuggingFace] {action_clean}" if action_clean else 'HuggingFace Activity',
            'description': f"{organization}: {action_clean}",
            'url': f"{base_url}/{organization}",
            'published_date': published_date,
            'categories': [],
            'organization': organization,
            'metadata': {
                'action': action_clean
            },
            'objects': objects
        }

        if activity['title'] or activity['objects']:
            activity_list.append(activity)

    # Remove duplicates
    dedup_list = [json.loads(entry) for entry in list({json.dumps(d) for d in activity_list})]

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

    # Save to JSON file
    try:
        json_path = parsed_dir / f'huggingface.json'
        with open(json_path, 'w') as f:
            json.dump(dedup_list, f, indent=4)
        
        # Only log if no data was written (special case)
        if len(dedup_list) == 0:
            logging.warning("No data written to %s - empty activity list", json_path)
    except IOError as e:
        logging.error(f"Error writing to file: {e}")

    return dedup_list


if __name__ == "__main__":
    activities = load_huggingface_html_files()
    post_process_huggingface(activities)