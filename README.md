# tech-econ

A curated directory of resources for tech economists, data scientists, and applied researchers.

**Live site:** [tech-econ.com](https://tech-econ.com/)

## What's Inside

- **Packages** - 188 Python/R libraries for econometrics, causal inference, experimentation
- **Datasets** - 243 industry datasets for e-commerce, advertising, experimentation
- **Learning** - 111 books, courses, blogs for applied economics
- **Talks** - 50 interviews and podcasts from chief economists
- **Papers** - Academic papers organized by research topic
- **Career** - 13 resources for job hunting and interviews
- **Community** - 63 conferences, research labs, events

## Features

- Semantic search with vector embeddings
- ML-based content ranking
- Dark mode support
- Favorites and reading history
- Interactive conference map

## Tech Stack

- **Site**: Hugo static site generator
- **Search**: Fuse.js + Pagefind + bge-large-en-v1.5 embeddings
- **Backend**: Cloudflare Workers + D1 Database
- **Ranking**: LightGBM model

## Development

```bash
hugo server              # Run locally
npm run build            # Build site + search index
```

Data lives in JSON files under `/data/`. See `template.txt` for content schemas.

## Contributing

- Submit via [Submit form](https://tech-econ.com/submit/)
- Or open a [GitHub Issue](https://github.com/rawatpranjal/tech-econ/issues)

## Author

[Pranjal Rawat](https://github.com/rawatpranjal)
