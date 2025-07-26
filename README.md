# AI-News-Direct
Collect AI News from multiple sources: RSS feeds, news releases, blog posts, and social activities from AI labs & companies.

## Available Feeds

This project generates both JSON data files and Atom/RSS feeds from AI organizations and sources.

### Atom/RSS Feeds (feeds/ directory)
Ready-to-use XML feeds for RSS readers:

**Direct Company Feeds:**
- [`anthropic_news.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/anthropic_news.xml) - Anthropic news releases
- [`anthropic_research.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/anthropic_research.xml) - Anthropic research publications  
- [`anthropic_engineering.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/anthropic_engineering.xml) - Anthropic engineering blog
- [`bytedance_seed_blog.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/bytedance_seed_blog.xml) - ByteDance Seed blog posts
- [`bytedance_seed_research.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/bytedance_seed_research.xml) - ByteDance Seed research papers
- [`openai.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/openai.xml) - OpenAI Research Index

**RSS/Atom Feed Sources:**
- [`openai_feeds.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/openai_feeds.xml) - OpenAI News official RSS feed content

**HuggingFace Activities:**
- [`huggingface.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/huggingface.xml) - Model releases, datasets, and papers from selected AI organizations

**Aggregated Organization Feeds:**
- [`anthropic_aggregated.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/anthropic_aggregated.xml) - All Anthropic content (News + Engineering + HuggingFace activities)
- [`bytedance_aggregated.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/bytedance_aggregated.xml) - All ByteDance content (News + Research + HuggingFace activities)
- [`openai_aggregated.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/openai_aggregated.xml) - All OpenAI content (News + Research Index + HuggingFace activities)
- [`meta_aggregated.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/meta_aggregated.xml) - Meta/Meta-Llama/Facebook activities from HuggingFace
- [`google_aggregated.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/google_aggregated.xml) - Google/DeepMind activities from HuggingFace
- [`microsoft_aggregated.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/microsoft_aggregated.xml) - Microsoft activities from HuggingFace

### JSON Data Files (data/parsed/ directory)
Raw structured data used to generate the XML feeds above.

## Usage

### Full Pipeline
1. **Fetch content**: `python core/fetcher.py` - Downloads HTML pages and RSS/Atom feeds
2. **Parse scraped content**: Run individual scrapers (`python scrapers/anthropic.py`, `python scrapers/openai.py`, etc.)
3. **Parse RSS/Atom feeds**: `python scrapers/feed_parser.py` - Converts XML feeds to JSON
4. **Create aggregated feeds**: `python core/aggregator.py` - Combines multiple sources per organization
5. **Generate XML feeds**: `python core/generator.py` - Creates final RSS/Atom XML files

### Individual Components
- **HTML scraping**: Individual scrapers in `scrapers/` directory
- **RSS/Atom parsing**: `python scrapers/feed_parser.py`
- **Organization aggregation**: `python core/aggregator.py [org_name]`
- **Feed generation**: `python core/generator.py`

### Configuration
- **Sites to fetch**: Edit `config/sites_config.json`
- **Organizations**: Edit `config/organizations.json`


## Data Sources

The system aggregates content from multiple sources:
- **Direct scraping**: Company websites and blogs
- **RSS/Atom feeds**: Official company RSS feeds  
- **HuggingFace**: Model releases, datasets, and research papers
- **Social platforms**: Activities across AI research platforms