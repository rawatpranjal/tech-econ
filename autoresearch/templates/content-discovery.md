# Discover New Content

## Objective
Find and add new high-quality resources to the tech-econ directory using
the automated discovery crawler.

## Primary Tool
Run `python3 scripts/discover_content.py` with appropriate flags:
```bash
# Dry run - see what would be found without adding
python3 scripts/discover_content.py --dry-run --verbose

# Run for a specific content type
python3 scripts/discover_content.py --type packages --limit 5 --verbose

# Full run
python3 scripts/discover_content.py --limit 15 --verbose
```

Requires env vars: BRAVE_API_KEY, TAVILY_API_KEY, OPENAI_API_KEY

## Iteration Goals
Each autoresearch iteration should improve the discovery system:

1. **Tune search queries** - Edit `scripts/discovery_queries.json` to add
   better queries, remove low-yield ones, expand to new categories
2. **Improve relevance judgment** - Adjust the LLM prompts in
   `scripts/discover_content.py` (RELEVANCE_PROMPT, EXTRACTION_PROMPT)
3. **Fix edge cases** - Handle new data formats, broken domains, etc.
4. **Expand coverage** - Add queries for underrepresented categories

## Manual Discovery (Fallback)
If the script can't find content for a category:
1. Read `template.txt` for the required schema
2. Use WebSearch/WebFetch to find resources manually
3. Add entries to the appropriate data/*.json file
4. Include ALL required fields per the template
5. Use existing categories (check what categories already exist)

## Constraints
- Only add REAL resources with working URLs
- Do NOT fabricate descriptions or features
- Use existing categories (do not create new ones)
- Limit to 5-15 new items per iteration (quality over quantity)
- Do NOT add items that already exist (check by URL and name)

## Verification
```bash
python3 scripts/validate_data.py
hugo --gc --minify
```

## Success Criteria
- All new items have valid, accessible URLs
- All required fields present per template.txt
- No duplicate URLs within same file
- Descriptions are accurate and informative
- Categories match existing ones
- Hugo build passes
