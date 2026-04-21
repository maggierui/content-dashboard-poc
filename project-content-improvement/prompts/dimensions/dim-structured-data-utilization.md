# Dimension: Structured Data Utilization

**Dimension ID**: `structured_data_utilization`  
**Category**: Query and answer design

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Evaluate **format and structure** in a content type-aware manner: tables, parameter/value lists, and code retrievability. When applicable, include supported operating systems/platforms and version requirements in a concise list or table to make platform prerequisites retrievable. This dimension does not assess prose quality, conceptual depth, or content strategy.

## Flag

**Apply rules appropriate to the content type** — parameter/table rules apply broadly; conceptual articles might not require the same structure as procedural articles.

- **Critical parameters buried in code blocks** — A large code block (≥100 tokens) contains critical defaults, configuration values, or constraints with no accompanying prose or table summary. "Surrounding context is clear" requires an explicit prose or table restatement of the key values — nearby text that does not name the values does not qualify.
- **Dense parameter prose** — Parameters, defaults, or option/constraint pairs buried in dense prose where individual values are hard to locate. Flag when a paragraph contains 3 or more parameters or parameter/description pairs that require significant parsing to extract.
- **Code snippets with low retrievability** — Small snippets (≤100 tokens) that use unlabeled placeholders (e.g., `<your-value>`) with no concrete prose example nearby, or that omit OS/shell/version qualifiers when the article itself shows the behavior varies by environment.
- **Large tables without retrieval context** — The chunker splits tables exceeding approximately 500 tokens (roughly 50+ rows, or fewer rows with consistently long cell values — full paths, URLs, or multi-sentence descriptions) into ~250-token pieces, repeating column headers on each piece. Flag a table when it is large enough to be split **and** the column labels are too generic to identify the entity or attribute being documented (e.g., bare "Name," "Value," "Type" without qualifying context) with no introductory sentence preceding the table to supply that entity context. When column labels are specific and self-describing, split pieces are retrievable without surrounding prose.

**Before concluding your analysis:** Scan every large code block (≥100 tokens) for critical defaults or configuration values — check whether a prose or table restatement of those specific values exists nearby; surrounding text that does not name the values does not qualify. Also scan for bullet lists with ≥3 items following a consistent name + description pattern; these are easy to overlook when the prose reads naturally. For small snippets (≤100 tokens), check for unlabeled placeholders with no concrete example nearby. Scan for tables likely to be split by the chunker — roughly 50+ rows, or fewer rows with consistently long cell values (full paths, URLs, or multi-sentence descriptions) — and check whether the column labels are specific enough to attribute split pieces without an introductory sentence.

## Don't flag

- A short paragraph or single parameter stated clearly in prose — prose is acceptable when the value is easy to locate.
- Multiple large code blocks (≥100 tokens) when surrounding context is clear — note their presence but do not flag.
- Large tables (50+ rows or long cell values) where column labels are specific enough to identify the entity and attribute — split pieces are self-attributing even without an introductory sentence.
- Smaller tables regardless of surrounding prose — below the split threshold, the table is always retrieved as a single unit with its full context.
- Content-type misalignment or filler prose — out of scope for this dimension.
- Conceptual articles that don't follow procedural table/list conventions — rules apply to content type.

## Fix preference

- Dense parameter prose (3+ parameters) → convert to a table or list
- Critical values buried in large code blocks → add a prose or table restatement adjacent to the block naming the specific values
- Large tables without retrieval context → make column labels specific enough to identify the entity and attribute (e.g., "VM Size Name" instead of "Name"); add an introductory sentence naming the entity when column labels alone cannot provide attribution; break the table into smaller tables if logical subdivisions exist
- Code snippets with low retrievability → replace unlabeled placeholders with concrete examples in adjacent prose; add OS/shell/version qualifiers if the article shows behavior varies by environment

## Quality benchmark

A high-quality article has: key parameters/constraints surfaced early in tables/lists; critical defaults in plain text.

## Retrieval benefits

- Tables and lists create discrete lexical anchors — individual cells index as separate token sequences, making specific values retrievable even when surrounding code blocks are excluded.
- Plain-text restatements of critical defaults survive code block exclusion (blocks ≥100 tokens are not indexed).
- Introductory sentences before large tables bind the table to its entity name, preserving attribution when the table spans chunk boundaries.
- Explicit placeholder examples and environment qualifiers in small snippets ensure the snippet's scope appears in indexed tokens, not just in prose that may land in a different chunk.

## Output format (JSON)

Return ONLY valid JSON (no markdown fences).

```json
{
  "dimension": "structured_data_utilization",
  "recommendations": [
    {
      "evidence": "<specific quote, section, or structure from article>",
      "action": "<imperative>",
      "impact": "<retrieval effect>"
    }
  ]
}
```

- Set `"recommendations": []` if the article meets the quality benchmark OR no high-confidence issues are found.
- Include multiple recommendations only when several distinct, high-confidence fixes are needed.

