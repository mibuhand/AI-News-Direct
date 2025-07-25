import json
from bs4 import BeautifulSoup
import os
from pathlib import Path
import logging
from datetime import datetime, timezone
import codecs
from dateutil import parser
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Directory containing the HTML files
project_dir = Path(__file__).resolve().parent.parent
html_dir = project_dir / 'html_cache'
parsed_dir = project_dir / 'parsed_data'
# Ensure parsed_data directory exists
parsed_dir.mkdir(exist_ok=True)


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


def find_article_date(soup, article_title):
    script_tag = soup.find('script', string=lambda text: 'self.__next_f.push([1,\"1d:[' in text)
    if not script_tag:
        logging.error("Script tag with 'self.__next_f.push([1,\"1d:[ not found")
        return None
    script_content = script_tag.get_text().strip().lower()
    title_index = script_content.rfind(article_title.lower())
    date_index = script_content.rfind('publishedon', 0, title_index)
    date_str = script_content[date_index+16:date_index+26]
    return date_str


def extract_html_data(soup, filename):
    base_url = 'https://www.anthropic.com'

    if 'news' in filename:
        tags = {
            'post_tag': 'a.PostCard_post-card__z_Sqq',
            'title_tag': 'h3.PostCard_post-heading__Ob1pu',
            'date_tag': 'div.PostList_post-date__djrOA',
        }
        page_type = 'news'
    elif 'engineering' in filename:
        tags = {
            'post_tag': 'a.ArticleList_cardLink__VWIzl',
            'title_tag': 'h3.display-sans-s',
            'title_tag_alt': 'h2.display-sans-l',
            'date_tag': 'div.ArticleList_date__2VTRg',
        }
        page_type = 'engineering'

    post_items = []
    for post in soup.select(tags['post_tag']):
        title_element = post.select_one(tags['title_tag'])
        if not title_element:
            title_element = post.select_one(tags['title_tag_alt'])
        title = title_element.get_text(strip=True)
        url = str(base_url) + str(post['href'])
        
        # Generate unique ID using high-cardinality fields (will be set after published_date)
        # item_id will be generated after published_date is calculated

        date_element = post.select_one(tags['date_tag'])
        if not date_element:
            date_str = find_article_date(soup, title)
            if date_str:
                published_date = datetime.strptime(date_str + ' 00:00', '%Y-%m-%d %H:%M').replace(tzinfo=timezone.utc).isoformat()
            else:
                published_date = datetime.now(timezone.utc).isoformat()
        else:
            date_str = date_element.get_text(strip=True)
            published_date = datetime.strptime(date_str, '%b %d, %Y').replace(tzinfo=timezone.utc).isoformat()
        
        # Generate unique ID using high-cardinality fields
        id_components = [
            "anthropic",
            title,
            url,
            published_date
        ]
        item_id = hashlib.md5("_".join(filter(None, id_components)).encode()).hexdigest()
        
        out_item = {
            'id': item_id,
            'source': 'anthropic',
            'type': page_type,
            'title': title,
            'description': '',
            'url': url,
            'published_date': published_date,
            'categories': [],
            'organization': 'Anthropic',
            'metadata': {},
            'objects': []
        }
        post_items.append(out_item)

    return post_items


def extract_script_data(soup):
    # Find the script tag containing the JSON data
    script_tag = soup.find('script', string=lambda text: 'self.__next_f.push([1,\"1d:[' in text)
    if not script_tag:
        logging.error("Script tag with 'self.__next_f.push([1,\"1d:[ not found")
        return None

    # Extract the JSON string from the script content
    script_content = script_tag.get_text().strip()
    first_index = script_content.find('[')
    last_index = script_content.rfind(']')
    second_index = script_content.find('[', first_index+1)
    second_last = script_content.rfind(']', 0, last_index)
    json_string = script_content[second_index:second_last+1]
    json_string = codecs.decode(json_string, 'unicode_escape')

    try:
        # Load the JSON data
        json_data = json.loads(json_string)[3]
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        return None

    return json_data


def parse_script_data(json_data):
    base_url = 'https://www.anthropic.com/research/'
    post_items = []
    for sections in json_data['page']['sections'][1]['tabPages']:
        if sections.get('label', '') == 'Overview':
            for section in sections['sections']:
                if section.get('title', '') == 'Publications':
                    for post in section['posts']:
                        title = post['title']
                        url = base_url + post['slug']['current']
                        
                        # Parse published date to ISO format
                        published_date = parser.isoparse(post['publishedOn']).replace(tzinfo=timezone.utc).isoformat()
                        
                        # Extract categories
                        categories = [subj['label'] for subj in post.get('subjects', [])]
                        
                        # Generate unique ID using high-cardinality fields
                        id_components = [
                            "anthropic_research",
                            title,
                            url,
                            post['publishedOn'],
                            "_".join(categories) if categories else ''
                        ]
                        item_id = hashlib.md5("_".join(filter(None, id_components)).encode()).hexdigest()
                        
                        # Check for external URL
                        external_url = ''
                        if isinstance(post.get('cta', ''), dict):
                            if len(post['cta'].get('url', '')) > 0:
                                external_url = post['cta']['url']
                        
                        post_data = {
                            'id': item_id,
                            'source': 'anthropic',
                            'type': 'research',
                            'title': title,
                            'description': '',
                            'url': url,
                            'external_url': external_url,
                            'published_date': published_date,
                            'categories': categories,
                            'organization': 'Anthropic',
                            'metadata': {},
                            'objects': []
                        }
                        post_items.append(post_data)
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

    if 'news' in filename:
        page_type = 'news'
    elif 'engineering' in filename:
        page_type = 'engineering'
    elif 'research' in filename:
        page_type = 'research'

    try:
        json_path = parsed_dir / f'anthropic_{page_type}.json'
        with open(json_path, 'w') as f:
            json.dump(dedup_list, f, indent=4)
            logging.info(f"Parsed data successfully written to '{json_path}'")
    except IOError as e:
        logging.error(f"Error writing to file: {e}")


if __name__ == "__main__":
    filenames = [
        'www_anthropic_com_research.html',
        'www_anthropic_com_news.html',
        'www_anthropic_com_engineering.html'
    ]

    for filename in filenames:
        soup = load_html(filename)
        if 'research' in filename:
            json_data = extract_script_data(soup)
            save_to_json(parse_script_data(json_data), filename)
        else:
            save_to_json(extract_html_data(soup, filename), filename)