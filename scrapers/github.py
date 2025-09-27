import json
from bs4 import BeautifulSoup
import os
from pathlib import Path
import logging
from datetime import datetime, timezone
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

    # Find GitHub configuration
    for site in sites_config:
        if site.get('organization_key') == 'github':
            return {
                'output_files': site.get('output_files', {}),
                'cache_files': site.get('cache_files', {})
            }

    raise ValueError("GitHub configuration not found in sites_config.json")

def load_html(filename):
    file_path = html_dir / filename
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
    return soup

def extract_trending_data(soup, timeframe='monthly'):
    """Extract trending repositories from GitHub trending page"""
    repositories = []
    base_url = 'https://github.com'

    # Find repository articles
    repo_articles = soup.find_all('article', class_='Box-row')

    for article in repo_articles:
        try:
            # Extract repository name and URL
            title_element = article.find('h2', class_='h3 lh-condensed')
            if not title_element:
                continue

            repo_link = title_element.find('a')
            if not repo_link:
                continue

            repo_name = repo_link.get_text(strip=True)
            repo_url = base_url + repo_link.get('href', '')

            # Extract org/repo path for deduplication
            repo_path = repo_link.get('href', '').strip('/')

            # Format title with proper spacing around forward slash
            if '/' in repo_path:
                formatted_title = repo_path.replace('/', ' / ')
            else:
                formatted_title = repo_name

            # Extract description
            description_element = article.find('p', class_='col-9 color-fg-muted my-1 pr-4')
            description = description_element.get_text(strip=True) if description_element else ''

            # Extract programming language
            language_element = article.find('span', itemprop='programmingLanguage')
            language = language_element.get_text(strip=True) if language_element else ''

            # Extract stars count
            stars_element = article.find('a', href=re.compile(r'/stargazers$'))
            stars_text = stars_element.get_text(strip=True) if stars_element else '0'
            # Clean stars text (remove commas and convert k to thousands)
            stars_clean = stars_text.replace(',', '')
            if 'k' in stars_clean.lower():
                stars_clean = stars_clean.lower().replace('k', '')
                try:
                    stars_count = int(float(stars_clean) * 1000)
                except:
                    stars_count = 0
            else:
                try:
                    stars_count = int(stars_clean)
                except:
                    stars_count = 0

            # Extract forks count
            forks_element = article.find('a', href=re.compile(r'/forks$'))
            forks_text = forks_element.get_text(strip=True) if forks_element else '0'
            # Clean forks text
            forks_clean = forks_text.replace(',', '')
            if 'k' in forks_clean.lower():
                forks_clean = forks_clean.lower().replace('k', '')
                try:
                    forks_count = int(float(forks_clean) * 1000)
                except:
                    forks_count = 0
            else:
                try:
                    forks_count = int(forks_clean)
                except:
                    forks_count = 0

            # Extract stars today (trending metric)
            stars_today_element = article.find('span', class_='d-inline-block float-sm-right')
            stars_today_text = stars_today_element.get_text(strip=True) if stars_today_element else '0 stars today'
            # Extract number from "X stars today" text
            stars_today_match = re.search(r'(\d+(?:,\d+)*)', stars_today_text)
            stars_today = int(stars_today_match.group(1).replace(',', '')) if stars_today_match else 0

            # Generate unique ID based on repository path (stable across updates)
            item_id = hashlib.md5(f"github_trending_{repo_path}".encode()).hexdigest()

            repository = {
                'id': item_id,
                'source': 'github',
                'type': 'trending_repository',
                'title': formatted_title,
                'description': description,
                'url': repo_url,
                'published_date': datetime.now(timezone.utc).isoformat(),
                'categories': [language] if language else [],
                'metadata': {
                    'stars': stars_count,
                    'forks': forks_count,
                    'stars_today': stars_today,
                    'language': language,
                    'timeframe': timeframe,
                    'repo_path': repo_path
                }
            }

            repositories.append(repository)

        except Exception as e:
            logging.warning(f"Failed to parse repository: {e}")
            continue

    return repositories

def deduplicate_repositories(all_repositories):
    """Deduplicate repositories by repo_path, keeping the one with highest stars_today"""
    repo_dict = {}

    for repo in all_repositories:
        repo_path = repo['metadata']['repo_path']

        # If this repo path hasn't been seen or has higher stars_today, keep it
        if (repo_path not in repo_dict or
            repo['metadata']['stars_today'] > repo_dict[repo_path]['metadata']['stars_today']):
            repo_dict[repo_path] = repo

    return list(repo_dict.values())

def save_to_json(repositories, output_filename):
    """Save repositories to JSON file"""
    # Sort by stars_today (trending metric) in descending order
    repositories.sort(key=lambda x: x['metadata'].get('stars_today', 0), reverse=True)

    json_path = parsed_dir / output_filename
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(repositories, f, ensure_ascii=False, indent=2)

    logging.info(f"Successfully saved {len(repositories)} trending repositories to {json_path}")

if __name__ == "__main__":
    config = load_config()
    cache_files = config['cache_files']
    output_files = config['output_files']

    all_repositories = []
    timeframes = ['daily', 'weekly', 'monthly']

    # Process each timeframe
    for timeframe in timeframes:
        cache_key = f'trending?since={timeframe}'
        cache_filename = cache_files.get(cache_key)
        individual_output = output_files.get(cache_key)

        if not cache_filename:
            logging.warning(f"No cache file configured for {cache_key}")
            continue

        file_path = html_dir / cache_filename
        if file_path.exists():
            logging.info(f"Processing GitHub trending file: {cache_filename}")
            soup = load_html(cache_filename)
            if soup:
                repositories = extract_trending_data(soup, timeframe)
                all_repositories.extend(repositories)

                # Save individual timeframe file
                if individual_output:
                    save_to_json(repositories, individual_output)
            else:
                logging.error(f"Failed to load HTML content for {cache_filename}")
        else:
            logging.warning(f"Cache file not found: {cache_filename}")

    # Deduplicate and save combined results
    if all_repositories:
        logging.info(f"Found {len(all_repositories)} total repositories before deduplication")
        deduplicated_repositories = deduplicate_repositories(all_repositories)
        logging.info(f"After deduplication: {len(deduplicated_repositories)} repositories")

        # Save combined deduplicated results
        combined_output = output_files.get('trending_combined', 'github_trends.json')
        save_to_json(deduplicated_repositories, combined_output)
    else:
        logging.error("No repositories found to process")