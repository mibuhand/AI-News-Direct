# AI-News-Direct
Collect AI news from direct scraping of company websites and blogs.

## Available Feeds

This project generates both JSON data files and Atom/RSS feeds from AI organizations.

### Atom/RSS Feeds (feeds/ directory)
Ready-to-use XML feeds for RSS readers:

**Direct Company Feeds:**

| Original Website | Feed URL |
|------------------|----------|
| [Anthropic News](https://www.anthropic.com/news) | [`anthropic_news.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/anthropic_news.xml) |
| [Anthropic Research](https://www.anthropic.com/research) | [`anthropic_research.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/anthropic_research.xml) |
| [Anthropic Engineering Blog](https://www.anthropic.com/engineering) | [`anthropic_engineering.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/anthropic_engineering.xml) |
| [ByteDance Seed Blog](https://seed.bytedance.com/blog) | [`bytedance_seed_blog.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/bytedance_seed_blog.xml) |
| [ByteDance Seed Research](https://seed.bytedance.com/research) | [`bytedance_seed_research.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/bytedance_seed_research.xml) |
| [OpenAI Research Index](https://openai.com/research) | [`openai_research.xml`](https://raw.githubusercontent.com/mibuhand/AI-News-Direct/main/feeds/openai_research.xml) |

### JSON Data Files (data/parsed/ directory)
Raw structured data used to generate the XML feeds above.

## Usage

### Full Pipeline
1. **Fetch content**: `python core/fetcher.py` - Downloads HTML pages from configured sites
2. **Parse scraped content**: Run individual scrapers (`python scrapers/anthropic.py`, `python scrapers/openai.py`, etc.)
3. **Generate feeds**: `python core/generator.py` - Creates feeds from parsed data

### Individual Components
- **HTML scraping**: Individual scrapers in `scrapers/` directory
- **Feed generation**: `python core/generator.py`

### Configuration
- **Sites to fetch**: Edit `config/sites_config.json`


## Data Sources

The system collects content from:
- **Direct scraping**: Company websites and blogs
  - Anthropic news, research, and engineering blog
  - ByteDance Seed blog and research
  - OpenAI research index

## To-Do
- Expand to additional AI labs and research organizations:
  - ElevenLabs blog and research
  - Hume ai blog and research
  - Runway research and announcements
  - Luma AI updates
  - Other AI research labs
- Add automated scheduling/monitoring