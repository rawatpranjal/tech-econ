# Books

Reference material used to drive improvements to the recsys / search stack.

Source PDFs are gitignored (see `.gitignore: books/**/source.pdf`). Only the
docling-converted markdown, extracted figures, and synthesis docs are checked in.

## Workflow for a new book

```bash
mkdir -p books/<slug>
mv path/to/book.pdf books/<slug>/source.pdf
docling books/<slug>/source.pdf --to md --output books/<slug>/
python3 scripts/split_book.py books/<slug>/
```

## Available books

- [`deep-learning-recsys/`](deep-learning-recsys/) — *Deep Learning Recommender Systems* — used to plan the May 2026 retrieval/ranking/reranking overhaul.
