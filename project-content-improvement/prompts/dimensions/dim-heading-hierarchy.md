# Dimension: Heading Hierarchy

**Dimension ID**: `heading_hierarchy`  
**Category**: Structural and chunking

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Assess whether headings function as **complementary, discriminative retrieval anchors**. The service **prepends H1 + containing H2 to every chunk**, so:

- **H1** establishes **stable scope** (product/solution + optional domain),
- **H2** expresses **specific task/intent** within that scope,
- **H3/H4** refine variants, tools, platforms, or step groups.

The combined H1 + H2 prefix MUST be self-descriptive and retrieval-safe (entity + task + key qualifier where needed).

## Key criteria

Evaluate heading quality against these rules:

1. **Complementary hierarchy** – H1 sets entity + domain scope; H2 states the primary task/intent within that scope; H3/H4 specialize (variants, OS, tools, tiers) rather than restating scope. Flag risk if H1 and H2 repeat the same information or compete for intent.
2. **Front-load high-signal tokens** – Front‑load distinctive terms in first 5–7 words; avoid generic starters ("Overview", "Introduction") unless paired immediately with discriminators.
3. **Require discriminative anchors** – Treat headings as discriminative when they include a product/feature name AND an action or intent (for example, "Contoso Storage: configure replication for premium tiers").
4. **Flag collisions and over-reuse** – Flag collisions when headings differ only by non-discriminative words, or when long H1s list tools/variants that get copied into every chunk (repeated-noise prefix). Flag weak H2s indistinguishable under a shared H1.
5. **Place tools/variants at lowest differentiating level** – Keep H1 minimal and stable; place tools, OS, tiers in H2 or H3 where they differentiate retrieval without polluting the repeated prefix.
6. **Accept scoped generics** – Accept a generic heading only if the containing H1 establishes unambiguous scope AND the immediate H2 or first paragraph provides a canonical disambiguator.
7. **Ignore tense variations** – Do not flag minor tense or phrasing variations (e.g., "configuring" vs "configure").

**Utility headings treatment:**

- "Next steps" and "See also" are navigational footers. IGNORE them completely when assessing headings.
- "Prerequisites" header is ignored (not flagged for lacking qualifiers) IF the H1 establishes clear product/operation scope.

## Quality benchmark

A high-quality article has: clear complementary hierarchy; H1 sets stable scope, H2 states task intent, H3/H4 refine; no collision or repeated-noise risk from H1/H2 prefix.

## Output format (JSON)

Return ONLY valid JSON (no markdown fences).

```json
{
  "dimension": "heading_hierarchy",
  "recommendations": [
    {
      "evidence": "<specific heading text or structure from article>",
      "action": "<imperative>",
      "impact": "<retrieval effect>"
    }
  ]
}
```

- Set `"recommendations": []` if the article meets the quality benchmark OR no high-confidence issues are found.
- Include multiple recommendations only when several distinct, high-confidence fixes are needed.
