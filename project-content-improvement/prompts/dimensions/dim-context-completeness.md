# Dimension: Context Completeness

**Dimension ID**: `context_completeness`  
**Category**: Structural and chunking

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Detect **missing context** that makes a retrieved chunk wrong or incomplete: unstated qualifiers, hidden dependencies, and weak entity signals in variant-specific content. Focus on *absent information* only — do not flag terms that are present but could be interpreted multiple ways. This dimension does not assess ambiguous meaning, naming inconsistencies, or heading structure.

## Flag

- **Hidden dependencies** — The instruction depends on an unstated prerequisite defined only in a section unlikely to appear in the top five retrieved chunks. Examples: steps reference a resource, variable, or role created in a distant prerequisite section with no local reminder; a procedure requires a specific SKU/tier but this is only mentioned in a different section; a step defers to an image, output, or result described in a sibling section (e.g., "the same as step 4 of the PySpark section") that will not be co-retrieved. Also flag vague backward-reference phrases — "as mentioned earlier," "as discussed in the previous section," "following the approach mentioned above," "building on the service options described above" — these create a retrieval dependency even when the referenced content exists elsewhere in the article. If the referenced content does not exist anywhere in the article at all, the dependency is unresolvable — flag it with higher severity since the reader cannot recover the information from any chunk. Example: "available in all regions except for the one mentioned previously" when no region is mentioned anywhere in the article.
- **Missing local qualifiers** — A procedure, parameter, or limit varies by platform (OS, version, architecture), operational context (region, SKU/tier, API version), or prerequisite (dependent features, roles, required setup) and the chunk does not state which variant applies. The qualifier must be present in the chunk body or unambiguously established in the prepended H1/H2. Examples: a command differs by OS but the section doesn't state which; a limit varies by region/version and the chunk states only one value without qualifying it; an instruction applies to "version X.Y or later" but provides no guidance for earlier versions — treat "X.Y or later" as one variant, and flag when other variants are left without coverage. Also applies to conceptual tab blocks (Azure CLI / PowerShell / Portal): the conceptual tab label is included in the chunk and functions as the primary qualifier identifying which platform or tool the instructions cover. Flag when a conceptual tab label is too generic to unambiguously identify the platform variant — for example, "CLI" instead of "Azure CLI," or "SDK" when multiple SDKs are covered in the article.
- **Weak entity signal in variant-specific content** — A section or table contains data, parameters, limits, or commands that are specific to the entity named in H1 or H2, but the body text never names the entity — it either uses only pronouns/demonstratives ("this service," "these VMs," "the series") or omits any entity reference entirely. Flag when the content would be unattributable without the prepended heading prefix. Structural heuristic: if the H1 or H2 contains a product, SKU, or variant name and the section contains a specs table, parameter list, or capability matrix, flag when the body never names that product or variant.

**Before concluding your analysis:** Scan explicitly for (1) vague backward-reference phrases ("as mentioned earlier," "as discussed above," "building on the above") that create retrieval dependencies, (2) vague operational qualifiers ("certain tiers," "select regions," "some versions") that leave variant eligibility unstated, and (3) conceptual tab blocks where any conceptual tab label is generic or ambiguous — the label is the platform qualifier in the chunk, and a vague label leaves the variant unidentified. All three patterns are easy to miss when a more prominent completeness issue is also present.

## Don't flag

- Qualifiers already established in the H1 or H2 heading that are not overridden later in the article.
- Platform-agnostic procedures — no qualifier is needed when steps work identically across variants.
- Terms that are present but could be interpreted multiple ways — that is a clarity issue, not a completeness issue.
- Inconsistent naming or spelling variations for the same entity.
- Universal qualifiers that are irrelevant to the given procedure (e.g., architecture when steps are architecture-agnostic, or region when the feature is available in all regions).
- Standard prerequisite dependencies that any practitioner would already have in place (e.g., "an Azure subscription," "Azure CLI installed") — these do not need inline restatement in every section.
- Explicit hyperlinks to other articles or sections — cross-article and within-article links are a normal referencing pattern, not a hidden dependency. A vague qualifier (e.g., "certain limitations") paired with an adjacent hyperlink that resolves the specifics is acceptable; the link provides the missing detail.

## Fix preference

- Hidden dependencies → add an inline restatement of the prerequisite or qualifier within the dependent section (e.g., "Requires the X role created in Prerequisites"); remove or replace vague backward-reference phrases with the actual information. For unresolvable references (where the information doesn't exist elsewhere in the article), replace the vague phrase with the actual information inline, or remove it entirely
- Missing local qualifiers → add the qualifier inline in the step or sentence where it applies; do not rely on a distant section to establish it. For conceptual tab blocks, replace a generic conceptual tab label with a specific, canonical identifier (e.g., "CLI" → "Azure CLI," "SDK" → "Python" or ".NET").
- Weak entity signal → name the entity explicitly in body text at least once per section; replace "this service," "these VMs," or similar demonstratives with the entity name

## Quality benchmark

A high-quality article has: each chunk self-sufficient for execution; prerequisites and dependencies explicit within the chunk or its prepended headings; platform and operational qualifiers present wherever procedures or parameters differ by variant; sections with variant-specific content name the entity in body text so the chunk is attributable without relying on the H1/H2 prefix.

## Retrieval benefits

- Self-contained chunks don't require co-retrieved prerequisite sections — the 5-chunk grounding budget can't guarantee co-retrieval of distant sections, so local restatements are the only reliable fix.
- Local qualifiers prevent the model from generalizing instructions to variants the chunk was not written for.
- Naming the entity in body text ensures correct attribution when the H1/H2 prefix alone is insufficient to identify which variant or product a chunk belongs to.

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

