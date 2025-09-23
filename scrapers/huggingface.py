import json
import asyncio
from curl_cffi.requests import AsyncSession
from pathlib import Path
import logging
from datetime import datetime, timezone, timedelta
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

    # Find Hugging Face configuration
    for site in sites_config:
        if site.get('organization_key') == 'huggingface':
            return {
                'output_files': site.get('output_files', {})
            }

    raise ValueError("Hugging Face configuration not found in sites_config.json")

async def fetch_trending_items(item_type='model', limit=20):
    """Fetch trending models or datasets from Hugging Face API"""
    async with AsyncSession() as session:
        try:
            # Fetch trending items using the trending API
            params = {
                'type': item_type,
                'limit': limit
            }

            response = await session.get(
                'https://huggingface.co/api/trending',
                params=params,
                impersonate="chrome120",
                timeout=10
            )
            response.raise_for_status()
            response_data = response.json()
            items_data = response_data.get('recentlyTrending', [])

            items = []
            for item in items_data:
                try:
                    repo_data = item.get('repoData', {})
                    item_id = repo_data.get('id', '')
                    if not item_id:
                        continue

                    # Extract item information
                    author = repo_data.get('author', '')
                    item_name = item_id.split('/')[-1] if '/' in item_id else item_id
                    tags = repo_data.get('tags', [])
                    downloads = repo_data.get('downloads', 0)
                    likes = repo_data.get('likes', 0)
                    created_at = repo_data.get('createdAt', '')
                    last_modified = repo_data.get('lastModified', '')
                    pipeline_tag = repo_data.get('pipeline_tag', '')

                    # Create description from available data
                    description_parts = []
                    if pipeline_tag:
                        description_parts.append(f"Type: {pipeline_tag}")
                    if downloads > 0:
                        description_parts.append(f"Downloads: {downloads:,}")
                    if likes > 0:
                        description_parts.append(f"Likes: {likes}")
                    if tags:
                        top_tags = tags[:3]  # Show first 3 tags
                        description_parts.append(f"Tags: {', '.join(top_tags)}")

                    description = "<br/>".join(description_parts)

                    # Create standard format entry
                    item_entry = {
                        "id": hashlib.md5(f"huggingface_{item_id}".encode()).hexdigest(),
                        "source": "huggingface",
                        "type": item_type,
                        "title": item_id,
                        "description": description,
                        "url": f"https://huggingface.co/datasets/{item_id}" if item_type == 'dataset' else f"https://huggingface.co/{item_id}",
                        "published_date": created_at or datetime.now(timezone.utc).isoformat(),
                        "categories": [pipeline_tag] if pipeline_tag else [],
                        "metadata": {
                            "author": author,
                            "item_name": item_name,
                            "downloads": downloads,
                            "likes": likes,
                            "last_modified": last_modified,
                            "all_tags": tags
                        }
                    }

                    items.append(item_entry)

                except Exception as e:
                    logging.warning(f"Failed to process {item_type} {item.get('repoData', {}).get('id', 'unknown')}: {e}")
                    continue

            return items

        except Exception as e:
            logging.error(f"Failed to fetch trending {item_type}s: {e}")
            return []

async def fetch_daily_papers():
    """Fetch daily papers from the last 30 days and return top papers by upvotes and GitHub stars"""
    async with AsyncSession() as session:
        all_papers = []

        # Get dates for the last 30 days starting from yesterday, but skip weekends
        today = datetime.now(timezone.utc)
        dates = []
        for i in range(1, 31):  # Start from 1 (yesterday) instead of 0 (today)
            date = today - timedelta(days=i)
            # Skip weekends (Saturday=5, Sunday=6)
            if date.weekday() < 5:  # Monday=0 to Friday=4
                dates.append(date.strftime('%Y-%m-%d'))

        logging.info(f"Fetching daily papers for {len(dates)} days...")

        for date in dates:
            try:
                response = await session.get(
                    f'https://huggingface.co/api/daily_papers?date={date}',
                    impersonate="chrome120",
                    timeout=10
                )
                response.raise_for_status()
                papers_data = response.json()

                # Add date info to each paper
                for paper in papers_data:
                    paper['fetch_date'] = date
                    all_papers.append(paper)

                logging.info(f"Fetched {len(papers_data)} papers for {date}")

            except Exception as e:
                logging.warning(f"Failed to fetch papers for {date}: {e}")
                continue

        if not all_papers:
            logging.error("No papers were fetched from any date")
            return []

        logging.info(f"Total papers collected: {len(all_papers)}")

        # Sort by upvotes and get top 6
        papers_by_upvotes = sorted(all_papers, key=lambda x: x.get('paper', {}).get('upvotes', 0), reverse=True)[:6]

        # Sort by GitHub stars and get top 6
        papers_by_stars = sorted(all_papers, key=lambda x: x.get('paper', {}).get('githubStars', 0), reverse=True)[:6]

        # Combine and deduplicate by paper ID
        combined_papers = papers_by_upvotes + papers_by_stars
        seen_ids = set()
        deduplicated_papers = []

        for paper_item in combined_papers:
            paper_data = paper_item.get('paper', {})
            paper_id = paper_data.get('id') or paper_item.get('title', '')
            if paper_id and paper_id not in seen_ids:
                seen_ids.add(paper_id)
                deduplicated_papers.append(paper_item)

        logging.info(f"Deduplicated to {len(deduplicated_papers)} unique papers")

        # Convert to standard format
        formatted_papers = []
        for paper_item in deduplicated_papers:
            try:
                paper_data = paper_item.get('paper', {})
                paper_id = paper_data.get('id', '')
                title = paper_item.get('title', '') or paper_data.get('title', '')
                summary = paper_item.get('summary', '') or paper_data.get('summary', '')
                authors = paper_data.get('authors', [])
                upvotes = paper_data.get('upvotes', 0)
                github_stars = paper_data.get('githubStars', 0)
                github_url = paper_data.get('githubRepo', '')
                project_url = paper_data.get('projectPage', '')
                published_date = paper_item.get('publishedAt', '') or paper_data.get('publishedAt', '') or paper_item.get('fetch_date', '')

                # Create description with key metrics
                description_parts = []
                if summary:
                    description_parts.append(summary[:200] + "..." if len(summary) > 200 else summary)
                if upvotes > 0:
                    description_parts.append(f"Upvotes: {upvotes}")
                if github_stars > 0:
                    description_parts.append(f"GitHub Stars: {github_stars}")
                # Extract author names from complex structure
                author_names = []
                for author in authors:
                    if isinstance(author, dict):
                        name = author.get('name', '')
                        if name:
                            author_names.append(name)

                if author_names:
                    description_parts.append(f"Authors: {', '.join(author_names[:3])}")

                description = "<br/>".join(description_parts)

                # Create URLs - prioritize ArXiv, then project page, then GitHub
                primary_url = f"https://arxiv.org/abs/{paper_id}" if paper_id else project_url or github_url or f"https://huggingface.co/papers/{paper_id}"

                # Add additional URLs as clickable links (excluding the primary URL)
                additional_links = []
                if github_url and github_url != primary_url:
                    additional_links.append(f"🔗 <a href=\"{github_url}\">GitHub</a>")
                if project_url and project_url != primary_url:
                    additional_links.append(f"🔗 <a href=\"{project_url}\">Project Page</a>")
                arxiv_url = f"https://arxiv.org/abs/{paper_id}" if paper_id else ""
                if arxiv_url and arxiv_url != primary_url:
                    additional_links.append(f"🔗 <a href=\"{arxiv_url}\">ArXiv</a>")
                hf_paper_url = f"https://huggingface.co/papers/{paper_id}"
                if hf_paper_url != primary_url:
                    additional_links.append(f"🔗 <a href=\"{hf_paper_url}\">Hugging Face</a>")

                if additional_links:
                    if description:
                        description += "<br/>" + "<br/>".join(additional_links)
                    else:
                        description = "<br/>".join(additional_links)

                external_url = github_url if primary_url != github_url else project_url if project_url != primary_url else None

                # Create standard format entry
                paper_entry = {
                    "id": hashlib.md5(f"huggingface_paper_{paper_id}".encode()).hexdigest(),
                    "source": "huggingface",
                    "type": "paper",
                    "title": title,
                    "description": description,
                    "url": primary_url,
                    "external_url": external_url,
                    "published_date": published_date or datetime.now(timezone.utc).isoformat(),
                    "categories": ["research", "paper"],
                    "metadata": {
                        "paper_id": paper_id,
                        "upvotes": upvotes,
                        "github_stars": github_stars,
                        "github_url": github_url,
                        "project_url": project_url,
                        "authors": author_names,
                        "summary": summary,
                        "fetch_date": paper_item.get('fetch_date', ''),
                        "num_comments": paper_item.get('numComments', 0),
                        "ai_summary": paper_data.get('ai_summary', ''),
                        "ai_keywords": paper_data.get('ai_keywords', [])
                    }
                }

                formatted_papers.append(paper_entry)

            except Exception as e:
                logging.warning(f"Failed to process paper {paper.get('id', 'unknown')}: {e}")
                continue

        return formatted_papers

async def main():
    """Main function to fetch and save Hugging Face trending models and datasets"""
    config = load_config()

    # Fetch trending models
    logging.info("Fetching Hugging Face trending models...")
    models = await fetch_trending_items('model')

    if models:
        output_file = parsed_dir / config['output_files']['trending_models']
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(models, f, ensure_ascii=False, indent=2)
        logging.info(f"Successfully saved {len(models)} models to {output_file}")
    else:
        logging.error("No models were fetched")

    # Fetch trending datasets
    logging.info("Fetching Hugging Face trending datasets...")
    datasets = await fetch_trending_items('dataset')

    if datasets:
        output_file = parsed_dir / config['output_files']['trending_datasets']
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(datasets, f, ensure_ascii=False, indent=2)
        logging.info(f"Successfully saved {len(datasets)} datasets to {output_file}")
    else:
        logging.error("No datasets were fetched")

    # Fetch daily papers
    logging.info("Fetching Hugging Face daily papers...")
    papers = await fetch_daily_papers()

    if papers:
        output_file = parsed_dir / config['output_files']['daily_papers']
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(papers, f, ensure_ascii=False, indent=2)
        logging.info(f"Successfully saved {len(papers)} papers to {output_file}")
    else:
        logging.error("No papers were fetched")

if __name__ == "__main__":
    asyncio.run(main())