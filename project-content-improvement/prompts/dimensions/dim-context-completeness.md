# Dimension: Context Completeness

**Dimension ID**: `context_completeness`  
**Category**: Structural and chunking

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Evaluate **informational sufficiency**: essential prerequisites and dependencies must be locally present inside the chunk OR clearly established in the prepended H1/H2 headings. Focus on *missing* required information only — do not flag terms that are present but unclear.

## Key criteria

Evaluate context completeness against these rules:

1. **Require local qualifiers** – Ensure required qualifiers and prerequisites are explicitly present and local for the procedure or reference: platform qualifiers (OS, version, architecture), operational qualifiers (region, SKU/tier, API version), and prerequisites (dependent features, roles, required setup).
2. **Accept heading-scoped context** – Consider a chunk complete when qualifiers and prerequisites are present in the chunk itself or unambiguously defined in the prepended H1/H2 and not overridden later.
3. **Skip irrelevant qualifiers** – Do not flag omission of qualifiers that are irrelevant to the given procedure (for example, architecture when steps are architecture-agnostic).
4. **Flag hidden dependencies** – Mark incompleteness only when the instruction or parameter depends on an unstated variant (different command per OS, region-specific limit, or feature-gated behavior) or on prerequisites that are defined only in sections unlikely to appear in the top five chunks (for example, "see previous section" for mandatory setup steps).

## Quality benchmark

A high-quality article has: each chunk self-sufficient; prerequisites/definitions inline or in prepended headings; platform and operational qualifiers present where procedures or parameters differ.

## Output format (JSON)

Return ONLY valid JSON (no markdown fences).

```json
{
  "dimension": "context_completeness",
  "recommendations": [
    {
      "evidence": "<specific quote, heading, or reference from article>",
      "action": "<imperative>",
      "impact": "<retrieval effect>"
    }
  ]
}
```

- Set `"recommendations": []` if the article meets the quality benchmark OR no high-confidence issues are found.
- Include multiple recommendations only when several distinct, high-confidence fixes are needed.
