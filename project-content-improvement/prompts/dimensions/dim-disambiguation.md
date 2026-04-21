# Dimension: Disambiguation

**Dimension ID**: `disambiguation`  
**Category**: Semantic and normalization

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Evaluate **clarity of meaning**: ambiguous terms must be explicitly scoped; multi-meaning terms must have sufficient context to resolve their intended meaning within an isolated chunk. Focus on *unclear meaning* only — do not flag missing prerequisites or absent qualifiers, and do not flag inconsistent naming patterns. This dimension does not assess missing information, naming inconsistencies, or structural issues.

## Flag

- **Ambiguous coreference** — A pronoun ("this," "it," "they") or referential noun phrase ("the service," "the component," "the configuration") appears where two or more entities in the chunk or heading could be the referent, creating genuine ambiguity about which entity is intended.
- **Multi-meaning terms without resolution** — A term with multiple possible meanings (e.g., "node," "gateway," "instance," "machine") is used with insufficient or conflicting context to determine its specific meaning in the chunk or its prepended heading. Example: "machine" sometimes meaning VM and sometimes host within the same section without clear definition.
- **Scope conflicts between heading and body** — Global scoping defined in H1/H2 is explicitly contradicted by a qualifier introduced in the body — not merely narrowed, but reversed or negated (e.g., H2 says "all regions" but body says "not available in X region without qualification"). The contradiction must be explicit; narrowing the H1/H2 scope to a specific case is acceptable and expected.

**Before concluding your analysis:** Scan explicitly for (1) pronoun chains — sequences of "it," "this," or "they" repeated across consecutive sentences where multiple entities have been introduced as plausible antecedents; (2) referential noun phrase chains — sequences of "the service," "the component," or similar noun phrases used where multiple entities could be the referent; and (3) scope-ambiguous relational phrases such as "other regions," "that environment," "this configuration," or "the previous deployment" where the intended referent requires context that will not be co-retrieved. All three patterns are easy to overlook when a multi-meaning term issue is also present.

## Don't flag

- Terms that have only one plausible meaning in the given context.
- Simple "this," "it," or referential noun phrases ("the service," "the component") where only one plausible antecedent exists.
- Missing platform or operational qualifiers (OS, version, region, SKU/tier, API version) — absent information is out of scope; this dimension only fires when a term could be *interpreted* in two or more ways.
- Inconsistent naming or alias variations for the same entity.
- Speculative ambiguity — only flag when ambiguity is demonstrably present: two meanings for the same term, two plausible antecedents for a pronoun or referential noun phrase, or scope that flips across sections.

## Fix preference

- Ambiguous coreference → replace the pronoun or referential noun phrase with the specific entity name
- Multi-meaning terms → add a parenthetical scope clarifier at first use in the section (e.g., "node (control plane node)")
- Scope conflicts → acknowledge the scope change explicitly (e.g., "except in X region") or restructure to separate global and scoped content into distinct sections

## Quality benchmark

A high-quality article has: all ambiguous terms scoped with sufficient context; no multi-meaning terms without clear resolution; no ambiguous coreference (pronouns or referential noun phrases with multiple plausible antecedents).

## Retrieval benefits

- Terms scoped to a single meaning produce consistent embeddings that match targeted queries reliably; ambiguous terms split the embedding signal across multiple meanings, reducing relevance for each.
- Resolved coreference (pronouns and referential noun phrases) removes conflicting context signals that weaken both keyword and semantic match scores for specific queries.
- Consistent scope between heading and body ensures both retrieval signals — keyword and semantic — point to the same answer; contradictory scope degrades ranking in hybrid search.

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

