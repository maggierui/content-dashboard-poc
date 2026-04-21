# Dimension: Heading Hierarchy

**Dimension ID**: `heading_hierarchy`  
**Category**: Structural and chunking

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Assess whether headings function as **complementary, discriminative retrieval anchors**. The service **prepends H1 + containing H2 to every chunk**, so the combined prefix must be self-descriptive, retrieval-safe, and human-readable. This dimension does not assess naming correctness, missing qualifiers, or section content quality.

- **H1** establishes **entity + broad intent** (product/solution + action/domain, e.g., "Plan and manage costs for Azure Blob Storage").
- **H2** should narrow to a **discriminative subtopic** (e.g., "Configure geo-redundant replication," "Redundancy in the primary region") or use an **accepted boilerplate term** (see Don't flag). In **variant- or version-specific articles** — where many sibling articles share identical H2 structure (e.g., every VM-series article has "Sizes," or every API-version article has "Breaking changes") — the H2 should restate the variant or version identifier to disambiguate (e.g., "Sizes in Fsv2-series," "Breaking changes in API 2024-01-01," "Version 12" → "Azure Blob Storage client library v12"), which also sharpens the embedding for opaque identifiers. In **regular articles** where H1 already names the entity, evaluate whether the **combined** H1+H2 prefix is discriminative — don't penalize an H2 just because it omits the entity name.
- **H3/H4** refine variants, tools, platforms, or step groups.

## Flag

- **H2 echoes H1 without narrowing** — H2 repeats the full H1 string or competes for the same scope instead of narrowing to a specific subtopic, phase, or aspect.
- **Generic H2 that is not discriminative** — H2 uses a bare category word ("Sizes," "Features," "Configuration," "Pricing," etc.) without naming the entity or a specific action. In **variant- or version-specific articles**, a bare category H2 is always a problem because dozens of sibling articles share the same H2. In **regular articles**, test against the combined H1+H2 prefix — if H1 already provides entity context that makes the prefix discriminative, do not flag. If H1 is also unscoped, boilerplate H2s are not exempt — flag both.
- **Heading collisions or repeated-noise prefix** — Multiple H2s differ only by non-discriminative words, or a long H1 lists tools/variants that get copied into every chunk as repeated noise.

**Before concluding your analysis:** For each candidate issue, mentally construct the full "H1 | H2" prefix and ask: *Is this combined prefix discriminative enough to distinguish chunks in this section from chunks in sibling articles — for both keyword and vector search?* For variant- or version-specific articles, also ask whether the H2 restates the variant or version identifier to sharpen the embedding. If the combined prefix is already discriminative, do not flag. Also check for H2s that merely restate the H1 without narrowing, and scan for bare category-word H2s that remain ambiguous even with the H1 prefix.

## Don't flag

- **Boilerplate H2 allowlist** — The following generic H2s are acceptable when the containing H1 already establishes unambiguous scope: "Overview," "Prerequisites," "Next steps," "See also," "Related content," "Limitations," "Known issues."
- **H2 already discriminative without entity** — H2 names a specific action, feature, or concept that is distinguishable on its own or becomes discriminative when combined with the H1 prefix (e.g., "Configure geo-redundant replication," "Redundancy in the primary region" under an entity-scoped H1). In regular articles, entity restatement is unnecessary when the combined H1+H2 prefix already disambiguates.
- **Entity restatement with narrowing** — H2 names the entity once while narrowing to a subtopic (e.g., `# Dasv6-series` → `## Sizes in Dasv6-series`). This is the preferred pattern when the subtopic word alone (e.g., "Sizes") would be ambiguous across articles.
- Minor tense or phrasing variations (e.g., "configuring" vs. "configure").

## Fix preference

- H2 echoes H1 → rewrite H2 to introduce a discriminative subtopic token not present in H1 (e.g., a specific action, phase, or aspect)
- Generic H2 in a **variant- or version-specific article** → restate the variant or version identifier in the H2 to disambiguate from sibling articles and sharpen the embedding for the opaque identifier (e.g., "Sizes" → "Sizes in Fsv2-series," "Breaking changes" → "Breaking changes in API 2024-01-01," "Version 12" → "Azure Blob Storage client library v12")
- Generic H2 in a **regular article** (combined prefix still ambiguous) → add a specific action or feature term to make the H1+H2 prefix distinguishable; add the entity name only if the H1 doesn't already provide it
- Heading collisions or repeated-noise prefix → remove shared boilerplate tokens from H2s so each is unique, or trim the H1 to only the core entity identifier

## Quality benchmark

A high-quality article has: H1 sets entity + broad intent; each H2 either narrows to a discriminative subtopic (alone or in combination with H1), uses an accepted boilerplate term, or — in variant- or version-specific articles — restates the variant or version identifier to disambiguate from sibling articles; no collision or repeated-noise risk from the H1/H2 prefix.

## Retrieval benefits

- The H1+H2 prefix is prepended to every chunk verbatim — entity-scoped, discriminative headings raise both keyword match rates and embedding relevance for targeted queries.
- Generic H2s ("Configuration," "Overview," "Pricing") appear across many articles; non-generic H2s prevent ranking collisions by differentiating chunks from sibling articles with similar structure.

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

