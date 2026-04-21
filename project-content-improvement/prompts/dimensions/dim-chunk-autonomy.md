# Dimension: Chunk Autonomy

**Dimension ID**: `chunk_autonomy`  
**Category**: Structural and chunking

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Evaluate **structural coherence and signal density**: each H2 section should serve a single intent — one user question, one procedure, or one concept — and the prose within it should be predominantly actionable, retrievable content rather than filler. When a section mixes unrelated intents, the chunker produces unfocused or arbitrarily split chunks. When a section is padded with low-signal prose, the resulting chunks dilute retrieval relevance even if the structure is sound. This dimension does not assess heading discrimination quality, naming consistency, missing qualifiers, or parameter formatting.

## Flag

- **Mixed intents under one H2** — A section serves multiple unrelated retrieval intents under a single H2. Signals include: abrupt intent shifts (procedure → conceptual background → troubleshooting) without clear separation, content that answers fundamentally different user questions under one heading, or transitional markers introducing unrelated concepts ("Additionally," "Separately," "Alternatively"). The trigger is mixed intents, not section length.
- **Multiple topics packed into a single conceptual tab** — A conceptual tab covers several distinct topics within one atomic unit: for example, a conceptual tab for "Configuration A" includes subsections for authorization, security, networking, and monitoring. Since each conceptual tab is retrieved as an indivisible atomic unit that cannot be split by subheadings, a multi-topic conceptual tab causes semantic dilution — the chunk's embedding blends unrelated concepts, reducing its similarity score for any single query.
- **Bold-text pseudo-headings in multi-subsection sections** — A section contains 3 or more **bold**-formatted labels acting as subsection dividers (e.g., **General recommendations**, **Security considerations**, **Considerations:**) instead of proper H3/H4 markdown headings. Chunking engines do not recognize bold as a structural boundary; the content cannot be independently retrieved or cleanly split.
- **Missing break points in dense sections** — A single-intent section spans multiple dense paragraphs with no H3/H4 subheadings, giving the chunker no clean break points and forcing mid-paragraph splits. This flag applies to multi-paragraph sections; a single dense paragraph that contains many sequential actions is a formatting issue, not a structural break point issue.
- **Low-signal prose diluting chunk retrieval** — A section is dominated by sentences that restate the heading without adding concrete facts, contain marketing adjectives without supporting data, or use filler phrases that contribute no retrievable information. Flag only when **3 or more consecutive sentences** match this pattern. Do not flag if removing the sentence would leave a gap in the technical content — that sentence carries signal.

**Before concluding your analysis:** Check explicitly for (1) bold-text labels acting as pseudo-headings in sections with 3 or more such labels, and (2) sections where low-signal filler outweighs actionable content. Both are easy to overlook when a mixed-intent issue is also present.

## Don't flag

- Well-structured H3/H4 hierarchies under an H2 — multiple subheadings under a shared parent are normal and expected. Do not recommend promoting H3s to H2s simply because multiple subheadings exist. If an H3 covers a fundamentally different user intent from its parent H2 (e.g., a troubleshooting H3 under a prerequisites H2, or a conceptual-background H3 under a procedure H2), treat the parent H2 section as mixed-intent and apply the "Mixed intents under one H2" flag instead.
- A conceptual tab that serves a single topic — combining conceptual and procedural guidance, pairing a command with an explanation of what it does, or opening with a brief lead-in sentence before its primary content all serve a single intent.
- Related subtopics grouped under a shared H2 (e.g., reference sections with multiple related tables for availability, durability, supported services).
- A single long table that documents one entity type or parameter set.
- Section length alone — flag only when intents are mixed, not because a section is long.
- Brief introductory or transitional sentences that orient the reader before technical content — a sentence or two of context is normal, not filler.
- Recommendation sentences at the end of a section (e.g., "We recommend using X for production workloads") — these carry retrieval signal.

## Fix preference

- Mixed intents → add H3 subheadings to separate intents within the existing H2; only split into a separate H2 when the content genuinely serves a different user intent
- Multiple topics packed into a single conceptual tab → promote the sub-topics (e.g., authorization, security, networking) to their own headings, and give each heading its own conceptual tab set focused on that single topic
- Bold pseudo-headings → convert bold labels to H3 (or H4) markdown headings so the chunker recognizes them as structural boundaries
- Missing break points in dense sections → add H3 subheadings at natural content boundaries to give the chunker clean split points
- Low-signal prose → remove or replace filler sentences with concrete technical content

## Quality benchmark

A high-quality article has: each H2 section serving a single intent; well-structured H3/H4 hierarchies under focused H2s; no unrelated topics mixed within sections; prose that is predominantly concrete, technical, and retrievable rather than filler.

## Retrieval benefits

- Single-intent sections produce focused chunks that match the user queries they answer; mixed-intent chunks score partially for multiple queries and rank first for none.
- H3 subheadings give the chunker clean break points — without them, splits occur mid-paragraph and can separate a question from its answer.
- Removing low-signal filler raises the effective frequency of technical terms in the chunk, improving match scores for both keyword and semantic retrieval.

## Output format (JSON)

Return ONLY valid JSON (no markdown fences).

```json
{
  "dimension": "chunk_autonomy",
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

