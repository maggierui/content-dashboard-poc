# Dimension: Entity Normalization

**Dimension ID**: `entity_normalization`  
**Category**: Semantic and normalization

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Promote **retrieval-safe naming**: entity names must be **correct** (canonical form used) and **consistent** (same form used throughout) in prose and headings. This dimension does not assess ambiguous meaning, structural issues, or missing information completeness.

## Flag

- **Non-canonical entity in a heading** — An H1 or H2 uses a non-canonical, abbreviated, or inconsistent entity name. These headings are prepended to every chunk and directly affect lexical matching. Exception: if the H1 already establishes the full canonical name, minor shortening in H2 is acceptable — see the "Minor shortening" entry in Don't flag.
- **Alias scattering** — Multiple names for the same concept appear in the article without a single canonical form established first (e.g., alternating between "Network Security Group," "NSG," and "security group" with no introduction pattern).
- **Non-canonical entity in body text** — A product, service, or feature name in the article body does not match the canonical form (e.g., a typo or incorrect variant like "RA-ZRS" where the canonical name is different). Even when only one form appears, a wrong name prevents retrieval for queries using the correct term.

**Before concluding your analysis:** Explicitly check H1 and every H2 for non-canonical or inconsistent entity names — headings affect every chunk in the article and are easy to overlook when body-text alias scattering is also present.

## Don't flag

- Canonical-first alias bridge followed by consistent short-form use (e.g., "Virtual Machine Scale Set (VMSS)" then "VMSS" throughout).
- Generic descriptor used after canonical first mention when unambiguous in context (e.g., "the scale set" after establishing "Virtual Machine Scale Set").
- Near-synonym variations on descriptive (non-product) terms where the semantic difference is negligible. Flag only when the variation is a named product, feature, or service — not informal descriptive language.
- Service/feature name vs. instance distinction — a capitalized feature name (e.g., "NodePool," "Eventhouse") used alongside a lowercase instance reference (e.g., "node pool," "eventhouse") is standard technical writing, not alias scattering.
- Legacy or transitional product names used as **actual technical surfaces** (resource provider namespaces, role names, API paths, CLI commands) — preserve these verbatim. Legacy names in headings or prose should use current branding; only the surface itself is exempt.
- Code identifiers, CLI commands, UI labels, or quoted portal text — these are fixed text and must not be altered.
- Minor shortening when H1 already establishes full scope (e.g., "Blob Storage" in H2 when H1 says "Azure Blob Storage").
- Capitalization-only differences (e.g., "zone redundant storage" vs. "Zone-redundant storage") — casing does not affect search or embedding similarity.
- Hyphenation-only differences (e.g., "zone-redundant storage" vs. "zone redundant storage") — tokenizers and embeddings normalize hyphens; no retrieval impact.
- Any case where you cannot confirm with high confidence that the form used differs from the canonical form. An incorrect entity name missed is recoverable; a correct term flagged as wrong and auto-fixed is not.

## Fix preference

- Non-canonical entity in heading → replace with the canonical form; check all H1s and H2s since they prefix every chunk in the article
- Alias scattering → establish the canonical form at first use; bridge known aliases with "(also known as X)" then use the canonical form consistently throughout
- Non-canonical entity in body → replace with the canonical form where confident; do not alter CLI commands, code identifiers, UI labels, or quoted portal text

## Quality benchmark

A high-quality article has: canonical forms consistent throughout; no alias scattering; stable entity names in headings.

## Retrieval benefits

- Scattered aliases fragment keyword match frequency across variant spellings — a single canonical term achieves higher term frequency than any alias alone, improving exact-match retrieval scores.
- Canonical terms embed predictably; scattered aliases dilute the embedding, reducing similarity to queries that use the standard term.
- Canonical names in headings strengthen the H1+H2 prefix prepended to every chunk — non-canonical names in headings reduce match rates for all chunks in the article.

## Output format (JSON)

Return ONLY valid JSON (no markdown fences).

```json
{
  "dimension": "entity_normalization",
  "recommendations": [
    {
      "evidence": "<specific quote, heading, or references showing inconsistency>",
      "action": "<imperative>",
      "impact": "<retrieval effect>"
    }
  ]
}
```

- Set `"recommendations": []` if the article meets the quality benchmark OR no high-confidence issues are found.
- Include multiple recommendations only when several distinct, high-confidence fixes are needed.

