# Dimension: Semantic Density

**Dimension ID**: `semantic_density`  
**Category**: Semantic and normalization

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Evaluate **information density**: high information-per-token within individual chunks; minimal filler/marketing. This dimension focuses exclusively on detecting low-signal prose, marketing language, and unnecessary filler.

## Key criteria

Evaluate semantic density against these rules:

1. **Flag low-signal prose** – Flag low-signal prose, fluff, and marketing boilerplate *inside* a chunk.
2. **Prefer concentrated signal** – Prefer one sharp intent with concentrated high-signal tokens (parameters, constraints, versions).
3. **Identify low-signal sentences** – Consider a sentence "low-signal" when it:
   - (a) restates the heading without adding concrete parameters, constraints, or outcomes
   - (b) contains marketing adjectives without factual data (e.g., "best-in-class", "easy to use")
   - (c) uses phrases that do not contribute retrievable facts
4. **Do not flag recommendations** – Sentences that recommend a specific product, feature, series, or approach (e.g., "we recommend X for Y workloads", "consider X first for mission-critical workloads") are a normal and important part of technical content. Do not flag them as low-signal or marketing language.
5. **Apply threshold** – Only recommend changes when more than ~25% of sentences in a section are low-signal by the above definition.
6. **Allow necessary transitions** – Allow brief transitions or narrative bridges if they supply necessary flow.

## Quality benchmark

A high-quality article has: high signal tokens concentrated; zero filler/ minimal marketing language; single intent per chunk; no low-signal sentences restating headings.

## Output format (JSON)

Return ONLY valid JSON (no markdown fences).

```json
{
  "dimension": "semantic_density",
  "recommendations": [
    {
      "evidence": "<specific low-signal sentence or quote from article>",
      "action": "<imperative>",
      "impact": "<retrieval effect>"
    }
  ]
}
```

- Set `"recommendations": []` if the article meets the quality benchmark OR no high-confidence issues are found.
- Include multiple recommendations only when several distinct, high-confidence fixes are needed.
