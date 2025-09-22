import json
import asyncio
from curl_cffi.requests import AsyncSession
from pathlib import Path
import logging
from datetime import datetime, timezone
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Directory setup
project_dir = Path(__file__).resolve().parent.parent
parsed_dir = project_dir / 'data' / 'parsed'
config_dir = project_dir / 'config'
parsed_dir.mkdir(exist_ok=True)

def load_config():
    """Load site configuration to get output filenames"""
    config_file = config_dir / 'sites_config.json'
    with open(config_file, 'r', encoding='utf-8') as f:
        sites_config = json.load(f)
    
    # Find Hacker News configuration
    for site in sites_config:
        if site.get('organization_key') == 'hackernews':
            return {
                'output_files': site.get('output_files', {})
            }
    
    raise ValueError("Hacker News configuration not found in sites_config.json")

async def fetch_best_stories(limit=50):
    """Fetch best stories from Hacker News API"""
    async with AsyncSession() as session:
        try:
            # Get list of best story IDs
            response = await session.get('https://hacker-news.firebaseio.com/v0/beststories.json', impersonate="chrome120", timeout=10)
            response.raise_for_status()
            story_ids = response.json()[:limit]  # Limit to top stories
            
            stories = []
            for story_id in story_ids:
                try:
                    # Fetch individual story details
                    story_response = await session.get(f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json', impersonate="chrome120", timeout=5)
                    story_response.raise_for_status()
                    story_data = story_response.json()
                    
                    if story_data and story_data.get('type') == 'story':
                        # Convert to standard format
                        original_url = story_data.get('url')
                        discussion_url = f"https://news.ycombinator.com/item?id={story_data['id']}"
                        
                        story = {
                            "id": hashlib.md5(f"hackernews_{story_data['id']}".encode()).hexdigest(),
                            "source": "hackernews",
                            "type": "story",
                            "title": story_data.get('title', ''),
                            "description": "",
                            "url": original_url or discussion_url,
                            "published_date": datetime.fromtimestamp(story_data.get('time', 0), tz=timezone.utc).isoformat(),
                            "categories": [],
                            "organization": "Hacker News",
                            "metadata": {
                                "score": story_data.get('score', 0),
                                "author": story_data.get('by', ''),
                                "comments": story_data.get('descendants', 0),
                                "hn_id": story_data['id']
                            },
                            "objects": []
                        }
                        stories.append(story)
                        
                except Exception as e:
                    logging.warning(f"Failed to fetch story {story_id}: {e}")
                    continue
            
            return stories
            
        except Exception as e:
            logging.error(f"Failed to fetch best stories: {e}")
            return []

async def main():
    """Main function to fetch and save Hacker News best stories"""
    config = load_config()
    
    logging.info("Fetching Hacker News best stories...")
    stories = await fetch_best_stories()
    
    if stories:
        output_file = parsed_dir / config['output_files']['beststories']
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(stories, f, ensure_ascii=False, indent=2)
        
        logging.info(f"Successfully saved {len(stories)} stories to {output_file}")
    else:
        logging.error("No stories were fetched")

if __name__ == "__main__":
    asyncio.run(main())