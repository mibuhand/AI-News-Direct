import json
import os
from pathlib import Path
from datetime import datetime, timezone
import logging
import glob

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Directory containing the parsed JSON files
project_dir = Path(__file__).resolve().parent.parent
parsed_dir = project_dir / 'data' / 'parsed'
config_dir = project_dir / 'config'

# Load organization configurations from JSON file
def load_organization_configs():
    """Load organization configurations from JSON file"""
    config_file = config_dir / 'organizations.json'
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading organization config: {e}")
        return {}

ORGANIZATION_CONFIGS = load_organization_configs()

def is_organization_match(org_name, patterns):
    """Check if an organization name matches any of the given patterns"""
    if not org_name or not patterns:
        return False
        
    org_lower = org_name.lower()
    return any(pattern.lower() in org_lower for pattern in patterns)

def aggregate_organization_feeds(org_key):
    """Aggregate feeds for a specific organization from multiple sources"""
    if org_key not in ORGANIZATION_CONFIGS:
        logging.error(f"Unknown organization key: {org_key}")
        return []
    
    config = ORGANIZATION_CONFIGS[org_key]
    aggregated_items = []
    
    # 1. Load direct feeds for this organization
    for filename in config['direct_feeds']:
        file_path = parsed_dir / filename
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    aggregated_items.extend(data)
                    logging.info(f"Added {len(data)} items from {filename}")
            except Exception as e:
                logging.error(f"Error reading {filename}: {e}")
    
    # 1.5. Load RSS/Atom feed sources for this organization
    for filename in config.get('feed_sources', []):
        file_path = parsed_dir / filename
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    aggregated_items.extend(data)
                    logging.info(f"Added {len(data)} items from RSS/Atom feed {filename}")
            except Exception as e:
                logging.error(f"Error reading feed source {filename}: {e}")
    
    # 2. Load and filter HuggingFace activities for this organization
    huggingface_file = parsed_dir / 'huggingface.json'
    if huggingface_file.exists():
        try:
            with open(huggingface_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            org_activities = []
            for item in data:
                org = item.get('organization', '')
                if is_organization_match(org, config['patterns']):
                    # Mark as aggregated source
                    item['source'] = f'{org_key}_aggregated'
                    item['original_source'] = 'huggingface'
                    org_activities.append(item)
            
            aggregated_items.extend(org_activities)
            logging.info(f"Added {len(org_activities)} {config['name']} activities from HuggingFace")
            
        except Exception as e:
            logging.error(f"Error reading huggingface.json: {e}")
    
    # 3. Sort all items by published_date (newest first)
    def get_date_for_sorting(item):
        date_str = item.get('published_date', '')
        if date_str:
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            except:
                pass
        return datetime.min.replace(tzinfo=timezone.utc)
    
    aggregated_items.sort(key=get_date_for_sorting, reverse=True)
    
    # No deduplication - delegate to individual parsers
    unique_items = aggregated_items
    
    # 5. Save aggregated feed
    try:
        output_file = parsed_dir / f'{org_key}_aggregated.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(unique_items, f, indent=4)
        
        logging.info(f"Created aggregated {config['name']} feed with {len(unique_items)} unique items")
        logging.info(f"Saved to: {output_file}")
        
        return unique_items
        
    except Exception as e:
        logging.error(f"Error saving aggregated feed: {e}")
        return []

def get_organization_stats(org_key):
    """Get statistics about organization-related content"""
    if org_key not in ORGANIZATION_CONFIGS:
        return {}
    
    config = ORGANIZATION_CONFIGS[org_key]
    stats = {}
    
    # Count direct feeds
    for filename in config['direct_feeds']:
        feed_name = filename.replace('.json', '')
        file_path = parsed_dir / filename
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    stats[feed_name] = len(data)
            except:
                stats[feed_name] = 0
        else:
            stats[feed_name] = 0
    
    # Count HuggingFace activities
    huggingface_file = parsed_dir / 'huggingface.json'
    if huggingface_file.exists():
        try:
            with open(huggingface_file, 'r') as f:
                data = json.load(f)
                org_count = sum(1 for item in data 
                               if is_organization_match(item.get('organization', ''), config['patterns']))
                stats[f'huggingface_{org_key}_orgs'] = org_count
        except:
            stats[f'huggingface_{org_key}_orgs'] = 0
    else:
        stats[f'huggingface_{org_key}_orgs'] = 0
    
    # Count total aggregated
    aggregated_file = parsed_dir / f'{org_key}_aggregated.json'
    if aggregated_file.exists():
        try:
            with open(aggregated_file, 'r') as f:
                data = json.load(f)
                stats['total_aggregated'] = len(data)
        except:
            stats['total_aggregated'] = 0
    else:
        stats['total_aggregated'] = 0
    
    return stats

def aggregate_all_organizations():
    """Aggregate feeds for all configured organizations"""
    results = {}
    
    for org_key in ORGANIZATION_CONFIGS.keys():
        logging.info(f"\nProcessing {ORGANIZATION_CONFIGS[org_key]['name']}...")
        
        # Show current stats
        stats = get_organization_stats(org_key)
        logging.info(f"Current {ORGANIZATION_CONFIGS[org_key]['name']} content stats:")
        for key, value in stats.items():
            logging.info(f"  {key}: {value} items")
        
        # Create aggregated feed
        aggregated_items = aggregate_organization_feeds(org_key)
        results[org_key] = aggregated_items
        
        # Show final stats
        final_stats = get_organization_stats(org_key)
        logging.info(f"Final {ORGANIZATION_CONFIGS[org_key]['name']} aggregated stats:")
        for key, value in final_stats.items():
            logging.info(f"  {key}: {value} items")
    
    return results

# Backward compatibility functions
def aggregate_bytedance_feeds():
    """Backward compatibility wrapper for ByteDance aggregation"""
    return aggregate_organization_feeds('bytedance')

def get_bytedance_stats():
    """Backward compatibility wrapper for ByteDance stats"""
    return get_organization_stats('bytedance')

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Aggregate specific organization
        org_key = sys.argv[1]
        if org_key in ORGANIZATION_CONFIGS:
            logging.info(f"Aggregating feeds for {ORGANIZATION_CONFIGS[org_key]['name']}...")
            
            # Show current stats
            stats = get_organization_stats(org_key)
            logging.info(f"Current {ORGANIZATION_CONFIGS[org_key]['name']} content stats:")
            for key, value in stats.items():
                logging.info(f"  {key}: {value} items")
            
            # Create aggregated feed
            aggregated_items = aggregate_organization_feeds(org_key)
            
            # Show final stats
            final_stats = get_organization_stats(org_key)
            logging.info(f"Final {ORGANIZATION_CONFIGS[org_key]['name']} aggregated stats:")
            for key, value in final_stats.items():
                logging.info(f"  {key}: {value} items")
        else:
            logging.error(f"Unknown organization: {org_key}")
            logging.info(f"Available organizations: {', '.join(ORGANIZATION_CONFIGS.keys())}")
    else:
        # Aggregate all organizations
        logging.info("Aggregating feeds for all organizations...")
        aggregate_all_organizations()