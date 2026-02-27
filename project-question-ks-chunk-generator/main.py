import sys
import os
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from common.data_models.retrieval_models import ArticlePerformance, RetrievalQuestion
from common.prompts import load_prompt
from common.send_openai_request import send_response_request
from common.batch import write_jsonl, send_batch, get_batch_results

def parse_questions_from_response(response: str) -> list[str]:
    """
    Parse the response text to extract both concise questions and BM25 keyword queries
    into a single list of strings.

    Handles lines like:
      "1. Concise question: How do I create a storage account ...?"
      "BM25 keyword query: New-AzStorageAccount create storage account ..."

    Also supports numbered lists, hyphen bullets, and labelled lines.
    """
    if not response:
        return []

    raw_lines = response.splitlines()
    extracted: list[RetrievalQuestion] = []

    for line in raw_lines:
        s = line.strip()
        if not s:
            continue

        # 1) Numbered lines: "1. ..." -> capture the remainder
        m_num = re.match(r'^\s*\d+\.\s*(.*)$', s)
        if m_num:
            content = m_num.group(1).strip()
            # If there's a label like "Concise question: ..." capture after the colon.
            if ':' in content:
                after = content.split(':', 1)[1].strip()
                if after:
                    extracted.append(RetrievalQuestion.create(after))
                    continue
            extracted.append(RetrievalQuestion.create(content))
            continue

        # 2) Hyphen / bullet lines: "- question ..." or "• question ..."
        m_bullet = re.match(r'^[\-\u2022]\s*(.*)$', s)
        if m_bullet:
            extracted.append(RetrievalQuestion.create(m_bullet.group(1).strip()))
            continue

        # 3) BM25 style lines beginning with BM25 (case-insensitive)
        m_bm25 = re.match(r'^(?:BM25\b.*?:\s*)(.+)$', s, flags=re.I)
        if m_bm25:
            extracted.append(RetrievalQuestion.create(m_bm25.group(1).strip()))
            continue

    return extracted


def main(article_performances: list[ArticlePerformance], output_dir: str, client=None):

    deployment_name = os.getenv("DEPLOYMENT_NAME", "gpt-5-mini")
    batch_deployment_name = os.getenv("BATCH_DEPLOYMENT_NAME", "gpt-5-batch")
    question_generator_batch_name = f"{output_dir}/question_batch.jsonl"

    question_generator_prompt = load_prompt("question_generator_article")
    for article in article_performances:
        if article.questions is None or len(article.questions) == 0:
            new_questions = True           
            if len(article_performances) == 1:
                result = send_response_request(deployment_name, question_generator_prompt, article.content, "low", client=client)
                article.questions = parse_questions_from_response(result)
            else:
                write_jsonl(question_generator_prompt, article.content, batch_deployment_name, article.content, question_generator_batch_name)

    if len(article_performances) > 1 and new_questions:
        # Send batch request
        batch_id = send_batch(question_generator_batch_name)
        batch_results = get_batch_results(batch_id)

        for article in article_performances:
            if article.questions is None or len(article.questions) == 0:
                article.questions = parse_questions_from_response(batch_results.get(article.relevant_path, ""))
    