# Dimension: Cross-Section Integrity

**Dimension ID**: `cross_section_integrity`  
**Category**: Redundancy and consistency

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Evaluate **cross-section consistency**: detect conflicting defaults, contradictory procedures, or inconsistent terminology across different sections of the article.

## Key criteria

Evaluate cross-section integrity against these rules:

1. **Check for value contradictions** – The same parameter, default, limit, or setting stated in Section A must match its value in Section B.
2. **Check for procedural contradictions** – Flag when different sections describe incompatible steps or sequences for the same operation.
3. **Check for terminology conflicts** – Flag when the same concept is described with conflicting definitions or names across sections.
4. **Check for version/date conflicts** – Flag when sections reference incompatible versions, deprecated features alongside current guidance, or outdated dates that contradict other sections.

**Threshold**: Only flag when two or more sections make contradictory claims about the same topic. Formatting or clarity issues within a single section are out of scope.

## Quality benchmark

A high-quality article has: no detectable conflicts; terminology and guidance consistent across sections; no contradictory parameter values, statements, or procedures.

## Output format (JSON)

Return ONLY valid JSON (no markdown fences).

```json
{
  "dimension": "cross_section_integrity",
  "recommendations": [
    {
      "evidence": "<specific quote, heading, or section references showing conflict>",
      "action": "<imperative>",
      "impact": "<retrieval effect>"
    }
  ]
}
```

- Set `"recommendations": []` if the article meets the quality benchmark OR no high-confidence issues are found.
- Include multiple recommendations only when several distinct, high-confidence fixes are needed.
