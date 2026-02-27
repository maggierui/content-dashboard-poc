# Dimension: Disambiguation

**Dimension ID**: `disambiguation`  
**Category**: Semantic and normalization

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Evaluate **clarity of meaning**: ambiguous terms must be explicitly scoped; pronouns must have clear antecedents; multi-meaning terms must have sufficient context. Focus on *unclear* meaning only — do not flag missing prerequisites or inconsistent naming patterns.

## Key criteria

Evaluate disambiguation against these rules:

1. **Use scope tokens** – Use scope tokens (OS, distro, version, architecture, region, SKU/tier, API version, feature flag) and nearby definitions to make the intended meaning of ambiguous terms clear.
2. **Flag multi-meaning terms** – Flag ambiguity when a term with multiple possible meanings (e.g., "node", "gateway", "instance", "machine") is used with insufficient or conflicting context to determine its specific meaning in this chunk or its prepended heading (for example, "machine" sometimes meaning VM and sometimes host without clear definition).
3. **Validate heading scope** – Accept global scoping defined in H1/H2 only if later chunks do not introduce conflicting local qualifiers; otherwise, require per-chunk qualifiers when a change in scope would alter the interpretation.
4. **Resolve pronouns** – Flag pronoun usage when the antecedent is not contained within the chunk or heading, or when multiple plausible antecedents exist.

## Quality benchmark

A high-quality article has: all ambiguous terms scoped (version/SKU/region); pronouns resolved within chunk or heading; no multi-meaning terms without clear context.

## Output format (JSON)

Return ONLY valid JSON (no markdown fences).

```json
{
  "dimension": "disambiguation",
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
