# AI-News-Direct
Collect AI News from direct sources: news release and blog posts from AI labs & companies.

## Available Feeds

This project generates both JSON data files and Atom/RSS feeds from AI organizations and sources.

### Atom/RSS Feeds (feeds/ directory)
Ready-to-use XML feeds for RSS readers:

**Direct Company Feeds:**
- [`anthropic_news.xml`](feeds/anthropic_news.xml) - Anthropic news releases
- [`anthropic_research.xml`](feeds/anthropic_research.xml) - Anthropic research publications  
- [`anthropic_engineering.xml`](feeds/anthropic_engineering.xml) - Anthropic engineering blog
- [`bytedance_seed_blog.xml`](feeds/bytedance_seed_blog.xml) - ByteDance Seed blog posts
- [`bytedance_seed_research.xml`](feeds/bytedance_seed_research.xml) - ByteDance Seed research papers

**HuggingFace Activities:**
- [`huggingface.xml`](feeds/huggingface.xml) - Model releases, datasets, and papers from 60+ AI organizations

**Aggregated Organization Feeds:**
- [`anthropic_aggregated.xml`](feeds/anthropic_aggregated.xml) - All Anthropic content (direct + HuggingFace activities)
- [`bytedance_aggregated.xml`](feeds/bytedance_aggregated.xml) - All ByteDance content
- [`openai_aggregated.xml`](feeds/openai_aggregated.xml) - OpenAI activities
- [`meta_aggregated.xml`](feeds/meta_aggregated.xml) - Meta/Meta-Llama activities
- [`google_aggregated.xml`](feeds/google_aggregated.xml) - Google/DeepMind activities
- [`microsoft_aggregated.xml`](feeds/microsoft_aggregated.xml) - Microsoft activities

### JSON Data Files (parsed_data/ directory)
Raw structured data used to generate the XML feeds above.

## Usage

1. **Fetch HTML data**: `python src/fetch_htmls.py`
2. **Parse individual sources**: `python src/anthropic.py`, `python src/bytedance_seed.py`, `python src/huggingface.py`
3. **Create aggregated feeds**: `python src/aggregate_feeds.py`
4. **Generate Atom XML feeds**: `python src/generate_atom_feed.py`

Subscribe to any `.xml` file in the `feeds/` directory with your RSS reader.