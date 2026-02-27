Generate exactly 5 article-specific customer questions from a single documentation article. For each question output two lines: (1) concise natural-language question (dense retrieval) and (2) BM25 keyword query (sparse retrieval). No extra commentary.

## Essentials

- Questions must be uniquely grounded in the article (not generic marketing or broad service intros).
- Questions must be grounded in content that is actually present in the article, not just a link to another article that describes the concept or task. For example, if an article has "To create a storage account, see [Create Storage Account]()." but does not directly show how to create a storage account, don't create a question like "How do I create a storage account?"
- Set must cover the article's most important topics, features, procedures, or troubleshooting points.
- Each question: single clear sentence, ideally 8–18 words (shorter allowed if still specific), no meta phrases, paraphrase headings.
- Avoid generic boilerplate questions like 'What is Azure Storage?' unless the article defines that concept (not merely mentions it).
- Include product or feature name in the question.
- For tutorials/quickstarts: Ask about the transferable knowledge (specific commands, configurations, parameter values) rather than the tutorial workflow itself (e.g., not "What are the steps in this quickstart?" but "What value should I set for the SKU parameter when creating X?"). Do not ask about how to delete tutorial resources.  
- Prohibit questions about minutiae in the article, such as "What API version is used in this example?"

## BM25 keyword query rules

- Lowercase tokens; no stop words unless part of identifiers/error codes/parameter names.
- Space-separated tokens; no punctuation except internal hyphens/colons inside literal identifiers.
- 5–12 tokens, ordered most specific → broader; include critical params, limits, flags, error codes, API versions if present.
- No invented terms or unseen synonyms; prefer singular unless plural is canonical.

## Validation before output

- Exactly 5 items numbered 1–5.
- Each item has lines labeled exactly "Concise question:" then "BM25 keyword query:".
- All questions grounded; BM25 lines contain only tokens (no trailing punctuation); intents distinct.

## Output format (strict, nothing else)

1. Concise question: <question_text>
   BM25 keyword query: <keyword_tokens>
2. Concise question: <question_text>
   BM25 keyword query: <keyword_tokens>
3. Concise question: <question_text>
   BM25 keyword query: <keyword_tokens>
4. Concise question: <question_text>
   BM25 keyword query: <keyword_tokens>
5. Concise question: <question_text>
   BM25 keyword query: <keyword_tokens>

If specificity is insufficient for BM25, include only grounded tokens, never invent. Do not wrap output in code fences or add explanations.