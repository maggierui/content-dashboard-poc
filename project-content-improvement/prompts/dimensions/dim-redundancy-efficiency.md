# Dimension: Redundancy Efficiency

**Dimension ID**: `redundancy_efficiency`  
**Category**: Redundancy and consistency

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Balance **chunk autonomy** against **result diversity**. Prefer **targeted, surgical redundancies** (especially in opening sentences) that sharpen embeddings without repeating large sections or polluting the prepended H1/H2 prefix.

## Key criteria

Evaluate redundancy against these rules:

1. **Distinguish functional from inefficient redundancy** – *Functional redundancy* (GOOD): short, chunk-local entity restatements in **opening sentences**, synonym bridges (canonical ↔ alias), safety notes for autonomy. *Inefficient redundancy* (BAD): copy-pasted paragraphs, repeating full entities in **headings**, boilerplate without added discrimination.
2. **Prefer opening-sentence reinforcement** – Entity and alias repetition belongs in the **first 1–2 sentences** under each H2 (embedded once per chunk), NOT in headings where H1/H2 already provide the prepended prefix.
3. **Allow short functional repetition** – Treat short repetition (1–2 lines restating entity/prerequisite) as acceptable when it sharpens embeddings; use **progressive shortening** once unambiguous ("the VM", "the cluster").
4. **Flag inefficient redundancy** – Flag when ≥2 paragraphs (>5 sentences) substantially duplicate earlier content, when ≥3 chunks repeat identical defaults without qualifiers, or when entity strings repeat across **sibling headings**.
5. **Suggest consolidation** – Suggest consolidation when duplicated lists across chunks share ≥70% identical items (move to single referenced section).

## Quality benchmark

A high-quality article has: minimal non-functional duplication; surgical opening-sentence reinforcement used appropriately; strong result diversity; no repeated boilerplate across sections.

## Output format (JSON)

Return ONLY valid JSON (no markdown fences).

```json
{
  "dimension": "redundancy_efficiency",
  "recommendations": [
    {
      "evidence": "<specific quotes or section references showing duplication>",
      "action": "<imperative>",
      "impact": "<retrieval effect>"
    }
  ]
}
```

- Set `"recommendations": []` if the article meets the quality benchmark OR no high-confidence issues are found.
- Include multiple recommendations only when several distinct, high-confidence fixes are needed.
