# Dimension: Chunk Autonomy

**Dimension ID**: `chunk_autonomy`  
**Category**: Structural and chunking

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Evaluate **structural coherence**: each section should be a single-topic, right-sized unit. Target 250–450 tokens (ideal single-chunk size). Sections exceeding 500 tokens will be split by the chunker at arbitrary boundaries. Focus on section size and topic boundaries only.

## Key criteria

Evaluate chunk autonomy against these rules:

1. **Avoid oversized sections** – Flag sections (>500 tokens) that exceed the chunk limit or cover too many concepts; these will be split by the chunker at arbitrary points, causing the author to lose control of semantic boundaries.
2. **Accept well-structured H3/H4 hierarchies** – H3 and H4 subheadings under an H2 are normal and expected. Do NOT recommend promoting H3s to H2s simply because multiple subheadings exist. Only flag structure issues when subheadings cover unrelated topics that don't belong under the same parent H2.
3. **Detect multi-topic spans** – Flag when a single section (regardless of subheadings) mixes unrelated intents that would confuse retrieval:
   - Abrupt intent shifts (procedure → conceptual background → troubleshooting) without clear separation
   - Content that answers fundamentally different user questions under one heading
   - Transitional markers introducing unrelated concepts ("Additionally", "Separately", "Alternatively")
4. **Accept single-entity tables** – Treat a single long table as acceptable when it documents a single entity type or parameter set.
5. **Skip precise counting** – Do not attempt precise token counting; instead, flag sections that clearly contain multiple *unrelated* retrieval answers.

**When NOT to recommend splitting:**
- Related subtopics are fine as H3s under a shared H2
- Reference sections with multiple related tables (e.g., availability, durability, supported services) are acceptable under one H2
- Subheadings that share a common parent concept should remain grouped

## Quality benchmark

A high-quality article has: sections sized within chunk limits (≤500 tokens, ideally 250–450); well-structured H3/H4 hierarchies under focused H2s; no unrelated topics mixed within sections.

## Output format (JSON)

Return ONLY valid JSON (no markdown fences).

```json
{
  "dimension": "chunk_autonomy",
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
