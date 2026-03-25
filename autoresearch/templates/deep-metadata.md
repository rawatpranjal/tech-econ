# Enrich Deep Metadata for Packages

## Objective
Add structured deep metadata to packages in `data/packages.json` to power
MCP tools and RAG search. Each package should get a `deep_metadata` object
with method-level detail, typed relationships, learning context, and
comparison notes.

## Current State
- Packages have surface-level metadata: name, description, tags, best_for,
  embedding_text, synthetic_questions, related_concepts, canonical_topics
- No method-level detail (can't search "which packages implement DML?")
- No typed relationships (related_packages is untyped flat list)
- No comparison context (can't answer "EconML vs CausalML")
- No prerequisite chains or key concepts for learning paths

## Strategy

Each iteration:
1. Find 5-10 packages in `data/packages.json` that lack `deep_metadata`
2. Prioritize by `model_score` (most-visited first), then alphabetically
3. For each package:
   a. Read the package's `github_url` or `docs_url` using WebFetch
   b. Extract deep metadata from the README/docs
   c. Add a `deep_metadata` object to the package entry
4. Validate: `python3 scripts/validate_data.py`

## Deep Metadata Schema

Each package gets a `deep_metadata` object with these fields:

```json
{
  "deep_metadata": {
    "methods": [
      {"name": "Method Name", "description": "One sentence", "category": "estimation|optimization|inference|visualization|testing|preprocessing"}
    ],
    "math_level": "none|basic-stats|linear-algebra|calculus|optimization-theory",
    "input_data_formats": ["pandas-dataframe", "numpy-array", "dict", "csv", "formula-syntax"],
    "output_types": ["point-estimates", "confidence-intervals", "posterior-distributions", "predictions", "plots", "model-objects", "causal-graphs"],
    "key_classes_functions": ["MainClass", "key_function"],
    "relationships": [
      {"target": "OtherPackage", "type": "builds-on|alternative-to|implements-paper|uses-dataset|prerequisite-for|complements|fork-of|successor-to", "note": "Why"}
    ],
    "prerequisite_chain": ["concept-1", "concept-2"],
    "key_concepts": [
      {"name": "Concept", "description": "One sentence explanation"}
    ],
    "typical_workflow": "Step 1 -> Step 2 -> Step 3 -> Step 4",
    "strengths": ["What it does well vs alternatives"],
    "limitations": ["When NOT to use it"],
    "comparison_notes": {
      "AlternativePackage": "How this differs from AlternativePackage"
    },
    "schema_version": "1.0",
    "extracted_from": ["https://github.com/..."],
    "extraction_date": "2026-03-25",
    "confidence": "high|medium|low"
  }
}
```

## Extraction Guidelines

- Use WebFetch to read actual docs/README before extracting
- List 3-8 specific methods per package
- Include 2-5 typed relationships per package
- 3-6 key concepts per package
- 2-4 strengths and limitations each
- Set confidence based on information quality

## Constraints
- Do NOT modify top-level fields (name, description, tags, model_score, etc.)
- Do NOT modify: hugo.toml, package.json, analytics-worker/, llm-worker/, CLAUDE.md, autoresearch/
- Do NOT delete any packages
- Do NOT hallucinate methods, papers, or packages not in docs
- Preserve valid JSON formatting (use 2-space indent)

## Verification
```bash
python3 scripts/validate_data.py
hugo --gc --minify
```

## Success Criteria
- All enriched packages have valid `deep_metadata` with `schema_version: "1.0"`
- Each has at least: methods (1+), relationships (1+), strengths (2+), limitations (1+)
- Relationship types use valid values only
- No regression in total package count
- JSON is valid and Hugo builds successfully
