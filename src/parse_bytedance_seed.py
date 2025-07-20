import json
from bs4 import BeautifulSoup
import os
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_router_data(file_path):
    # Read the HTML file
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

    # Find the script tag containing window._ROUTER_DATA
    script_tag = soup.find('script', string=lambda text: 'window._ROUTER_DATA' in text)
    
    if not script_tag:
        logging.error("Script tag with window._ROUTER_DATA not found")
        return None

    # Extract the JSON string from the script content
    script_content = script_tag.get_text().strip()
    json_start_index = script_content.find('{')
    json_string = script_content[json_start_index:]

    try:
        # Load the JSON data
        router_data = json.loads(json_string)
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        return None

    return router_data


if __name__ == "__main__":
    # Directory containing the HTML files
    project_dir = Path(__file__).resolve().parent.parent
    html_dir = project_dir / 'html_cache'

    for filename in os.listdir(html_dir):
        if "seed_bytedance" in filename and filename.endswith('.html'):
            file_path = os.path.join(html_dir, filename)
            router_data = extract_router_data(file_path)
            if router_data is not None:
                logging.info(f"Data from {filename}:")
                logging.info(router_data)
