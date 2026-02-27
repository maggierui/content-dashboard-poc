# Dimension: Entity Normalization

**Dimension ID**: `entity_normalization`  
**Category**: Semantic and normalization

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Promote **retrieval-safe, consistent canonical naming** in prose and headings while **preserving exactness for UI labels and code identifiers**. Consistent entities improve **lexical matching** (exact token hits), **embedding coherence** (canonical terms cluster predictably), and **reranker confidence** (unambiguous entity references reduce false positives). Catch egregious cross-technology errors (e.g., ".NET" in a Python article, "blobs" in Azure Files content) that cause mis-retrievals.

## Key criteria

Evaluate entity normalization against these rules:

1. **Flag cross-technology errors** – Flag egregious mismatches where entities from unrelated technologies appear (e.g., ".NET" references in Python-focused content, "blob" terminology in Azure Files articles, PowerShell cmdlets in Azure CLI guides). These indicate content misalignment or copy-paste errors.
2. **Distinguish feature names from descriptors** – Differentiate official feature names (e.g., "NodePool") from generic descriptors ("node pool"). Require canonical on first use; allow descriptor thereafter if unambiguous.
3. **Respect context: UI vs prose vs code** – **UI labels**: reproduce exact case/spelling, preferably formatted. **Prose**: follow style-guide grammar. **Code/inline code**: treat as identifiers—do NOT normalize (`protocolSettings` ≠ `PROTOCOL_SETTINGS`).
4. **Accept canonical-first pattern** – Accept canonical term followed by parenthetical alias on first use (e.g., "Virtual Machine Scale Set (VMSS)"); allow short form thereafter.
5. **Flag alias scattering** – Flag only when multiple aliases for the **same concept** appear without a canonical anchor. Scattered aliases fragment lexical matching and create inconsistent embedding neighborhoods.
6. **Maintain stable token boundaries** – Use stable, canonical entity names in prose headings (H1/H2 are prepended to every chunk) for lexical discrimination; do NOT alter tokenization inside identifiers or UI labels.
7. **Respect transitional naming** – For rebrands, prefer current product name in prose/headings but preserve legacy names where they remain actual surfaces (resource providers, roles, namespaces).
8. **High-confidence threshold** – Only recommend changes when ≥2 instances occur within the same context AND there is clear risk of user misunderstanding or retrieval error. Suppress low-confidence or speculative recommendations.

## Quality benchmark

A high-quality article has: canonical forms consistent throughout; UI labels and identifiers preserved exactly; no cross-technology errors; no alias scattering; stable entity names in headings.

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
