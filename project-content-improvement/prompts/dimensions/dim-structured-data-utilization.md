# Dimension: Structured Data Utilization

**Dimension ID**: `structured_data_utilization`  
**Category**: Query and answer design

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Evaluate **format and structure**: tables, parameter/value lists, numbered steps, and code quality. Surface rare/high-signal parameters or constraints early. When applicable, include supported operating systems/platforms and version requirements in a concise list or table to make platform prerequisites retrievable. Do not flag content-type misalignment or filler prose.

## Key criteria

Evaluate structured data utilization against these rules. **Apply rules appropriate to the content type** — procedural rules (numbered steps, success criteria) apply to how-to and quickstart articles; parameter/table rules apply broadly; conceptual articles might not require procedural structure.

1. **Understand code handling** – Code sample handling is size-aware. Small code snippets (≤100 tokens) are included in the chunk and may serve as lexical anchors (commands, flags, short examples). Large code blocks (≥100 tokens) are excluded from indexing. If an article contains multiple large code blocks, inform but do not flag as long as surrounding context is clear.
2. **Surface parameters in plain text** – Favor placing critical defaults, parameters, and constraints in plain text or tables so anchors survive even when large code is removed.
3. **Validate image alt text** – When images are present, verify that `alt` text carries concise, factual anchors (entities, parameter names/values, UI states) rather than decorative captions.
4. **Convert prose to structure** – Recommend conversion to a table/list when prose includes multiple related parameters or option/constraint pairs (suggest threshold: ≥3 related parameters); for single-parameter defaults or a lone option, prose is acceptable.
5. **Require success criteria** – Flag procedures lacking explicit success criteria (e.g., an end-state, verification command or UI confirmation) and suggest adding a one-line success check.
6. **Use numbered steps** – Prefer numbered steps when there are more than five sequential actions or when steps require parameters/flags to be specified.
7. **Flag oversized tables** – When a table clearly exceeds ~400 tokens (the usable budget after H1+H2 prepend), flag it. Continuation chunks lose the header row, making rows uninterpretable. Only flag when the table is unambiguously too large (rough guide: >8 rows at 5+ columns, or >15 rows at 3–4 columns). Suggest splitting by logical group under separate headings, or adding a one-line prose summary before the table so key entities survive in the first chunk.

**Helpful checks for small code snippets (≤100 tokens):**

- Use concise, copy‑paste friendly commands with explicit flags; avoid vague prose references.
- Keep the snippet immediately adjacent to the parameters/constraints it demonstrates so lexical anchors (names, flags, values) co‑locate with the explanation.
- Add clear qualifiers nearby (OS/shell/version/region/SKU) when behavior differs across variants to reduce false positives in hybrid retrieval.
- Multi‑line examples are common in languages like .NET/Python; do not flag small, multi-line snippets when focused and well-formed. For long CLI examples, prefer splitting into clear single‑line steps while staying ≤100 tokens per snippet.
- Prefer parameterized examples over placeholders; when placeholders are necessary, label them explicitly (e.g., `<RESOURCE_GROUP>`), and include one concrete example value in prose to strengthen anchors.
- Include one short expected output line or success indicator (command output, return code, UI state) in prose near the snippet to enable answer extraction even if the code is removed.
- Avoid environment‑specific assumptions (paths, profiles) unless qualified; if required, state the preconditions in a single sentence near the snippet.
- Keep tokens tight: remove non‑essential comments/whitespace; use the smallest snippet that still demonstrates the actionable step.
- Flag copy-paste breaking issues: command typos (e.g., `az stroage`), typographic characters (en-dashes, curly quotes instead of hyphens/straight quotes), and formatting artifacts (stray backticks, broken escape sequences).

## Quality benchmark

A high-quality article has: key parameters/constraints surfaced early in tables/lists; procedures numbered with success criteria; critical defaults in plain text; alt text with factual anchors.

## Output format (JSON)

Return ONLY valid JSON (no markdown fences).

```json
{
  "dimension": "structured_data_utilization",
  "recommendations": [
    {
      "evidence": "<specific quote, section, or structure from article>",
      "action": "<imperative>",
      "impact": "<retrieval effect>"
    }
  ]
}
```

- Set `"recommendations": []` if the article meets the quality benchmark OR no high-confidence issues are found.
- Include multiple recommendations only when several distinct, high-confidence fixes are needed.
