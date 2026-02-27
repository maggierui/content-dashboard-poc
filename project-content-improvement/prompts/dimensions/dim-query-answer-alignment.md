# Dimension: Query-Answer Alignment

**Dimension ID**: `query_answer_alignment`  
**Category**: Query and answer design

Apply shared foundation rules (style, recommendation stability).

**Only recommend changes with high confidence** — when there is clear evidence of retrieval risk or user confusion.

## Focus

Ensure the article answers the questions users are most likely to ask, with answers that are direct, front-loaded, and extractable within a single chunk.

## Evaluation process

### Step 1: Identify content type and infer likely questions

Based on the article's topic and structure, determine the primary content type. Then infer 3-5 likely user questions based on the query categories that content type should answer:

| Content Type | Expected Query Categories | Question Patterns to Infer |
|--------------|---------------------------|---------------------------|
| **Conceptual** | Descriptions/Definitions, Fact-finding | "What is [X]?", "Tell me about [X]", "How does [X] work?", "What are the limits of [X]?", "What are the requirements for [X]?" |
| **Procedural (how-to)** | Procedural, Coding/scripting | "How do I [action]?", "What are the prerequisites for [X]?", "How do I verify [X] worked?", "What is the syntax for [command]?" |
| **Troubleshooting** | Troubleshooting | "Why is [symptom] happening?", "How do I fix [error]?", "What causes [problem]?", "How do I resolve [issue]?" |
| **Quickstart** | Procedural, Navigational | "How do I get started with [X]?", "What is the fastest way to [action]?", "How do I set up [X]?", "Where do I find [X] in the portal?" |
| **Best practices** | Decision-making, Fact-finding | "What is the recommended way to [action]?", "When should I use [X] vs [Y]?", "What are the best practices for [X]?", "How do I decide between [options]?" |
| **Code reference** | Coding/scripting, Fact-finding | "What are the parameters for [API/command]?", "What is the syntax for [X]?", "Show me an example of [usage]", "What are the return values for [method]?" |

### Step 2: Verify each question has a direct, extractable answer

For each inferred question, check:

1. **Answer exists** — Is there content that directly answers this question?
2. **Answer is front-loaded** — Is the answer in the first 1-2 sentences after the relevant heading (not buried mid-paragraph)?
3. **Answer is autonomous** — Can the answer be understood without requiring context from other sections?
4. **Minimal preamble before answer** — Is the answer reachable within 1-2 sentences? Brief transitional sentences that orient the reader are acceptable; only flag extended preamble that delays the answer (e.g., multiple sentences of background before stating the key fact).

### Step 3: Apply content-type-specific criteria

1. **Conceptual** – Term + key attributes + purpose answerable in one chunk; lead sentence defines or explains; facts (limits, requirements) stated directly without narrative preamble.
2. **Procedural (how-to)** – Numbered steps + prerequisites + success criteria; includes explicit verification step (command, output, UI state) when steps produce changes; code examples are complete and runnable.
3. **Troubleshooting** – Symptom → cause → solution flow; each symptom mapped to cause and resolution (flag orphaned symptoms or fixes without causes).
4. **Quickstart** – Minimal prerequisites + fastest path to working result; clear end-to-end flow; navigational guidance included when portal steps are involved.
5. **Best practices** – Clear recommendations with rationale; comparison criteria when multiple options exist; scenario-based guidance for when to apply each practice.
6. **Code reference** – Complete syntax + parameters + return values; copy-paste ready examples; constraints and edge cases documented.

### General rules

- Each answer must be extractable from a single autonomous chunk.
- For hybrid articles (e.g., tutorials combining concept + procedure), evaluate each section against its own intent rather than forcing a single primary type. Infer questions for both conceptual ("What is [X]?") and procedural ("How do I [action]?") elements.
- Flag questions that are likely but unanswered, or answered only partially.
- Focus on whether likely questions have direct, extractable answers. Do not flag filler language, missing tables, or section sizing.

## Quality benchmark

A high-quality article:
- All inferred likely questions are answered
- Answers are front-loaded (first 1-2 sentences after relevant heading)
- Each answer is extractable from a single autonomous chunk
- Minimal preamble — brief transitions are acceptable, but answers are reachable within 1-2 sentences
- Content type structure is optimized for its intent

## Output format (JSON)

Return ONLY valid JSON (no markdown fences).

**Important**: Include `article_type` to document the inferred content type. Only generate recommendations for questions that are unanswered, buried, or partial.

```json
{
  "dimension": "query_answer_alignment",
  "article_type": "<Conceptual|Procedural|Troubleshooting|Quickstart|Best practices|Code reference>",
  "recommendations": [
    {
      "question": "<likely user question that is not well-answered>",
      "issue": "<add-summary|add-heading|restructure|complete-answer|add-content>",
      "evidence": "<specific quote, heading, or structure showing the problem>",
      "action": "<imperative fix>",
      "impact": "<retrieval effect>"
    }
  ]
}
```

**Issue values (action-oriented):**
- `add-summary` — Answer exists but needs a front-loaded summary sentence before details
- `add-heading` — Answer exists but lacks a query-matching heading for discoverability
- `restructure` — Answer should move earlier in the section to improve extractability
- `complete-answer` — Answer is partial or requires other sections; add missing context within the chunk
- `add-content` — No content answers this likely question; add new content

- Set `"recommendations": []` if all inferred questions are well-answered and extractable.
- Only include questions that need improvement — do not list well-answered questions.
