import requests
import time
import random
import urllib.parse
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from common.token_provider import TokenProvider

_token_provider = TokenProvider("https://learn.microsoft.com/.default")

def call_knowledge_service(question, token_provider=_token_provider, top_k=5):
    bearer_token = token_provider.get_token()
    headers = {
        'Content-Type': 'application/json', 
        'Authorization': f'Bearer {bearer_token}'
    }

    data = {'input': question}
    
    url = "https://learn.microsoft.com/api/v1/knowledge-search?api-version=2023-11-01-preview"

    if top_k != 5:
        url = f"{url}&top={top_k}"

    response = requests.post(url, headers=headers, json=data).json()

    return response

def get_chunk_preview(url: str, token_provider=_token_provider) -> dict:
    """
    Get the chunk preview for a Microsoft Learn article.
    
    Args:
        url: The Microsoft Learn article URL (e.g., https://learn.microsoft.com/en-us/azure/virtual-machines/sizes/general-purpose/dasv6-series)
        token_provider: Token provider for authentication
        
    Returns:
        dict: The chunk preview response from the Knowledge Service
    """
    bearer_token = token_provider.get_token()
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {bearer_token}'
    }
    
    data = {'url': url}
    endpoint = "https://learn.microsoft.com/api/search/chunkpreview"
    
    response = requests.post(endpoint, headers=headers, json=data, timeout=30)
    
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        print(f"Status: {response.status_code}")
        print(f"Response text: {response.text[:500]}")
        raise
    except Exception as e:
        print(f"Error getting chunk preview: {e}")
        raise


def call_test_knowledge_service(question, top_k=5):
    # url encode the question
    encoded_question = urllib.parse.quote(question)
    
    url = "https://knowledgebase-app.agreeableforest-13073a28.westus.azurecontainerapps.io/api/search/vector?"
    url += "query=" + encoded_question + "&experiment=chunk-8000&maxTokens=5000"
    # &branch=pr-en-us-9373

    if top_k != 5:
        url = f"{url}&top={top_k}"

    response = requests.get(url, timeout=30)
    
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        raise
    except Exception as e:
        print(f"JSON parse error: {e}")
        print(f"Status: {response.status_code}")
        print(f"Response text: {response.text[:500]}")
        raise
    

def parse_results(results) -> list[dict]:
    chunks = []
    items = results.get("value") or results.get("items") or []
    for item in items:
        content = item["chunk"]
        url = item["url"]

        #chunk_content = f"URL: {url}\n\nContent: {content}"
        chunk_data = {"url": url, "content": content}
        chunks.append(chunk_data)
    return chunks

def process_single_question(question: str, top_k: int) -> list[dict]:
    """Process a single question and return the evaluation data."""
    max_retries = 3
    base_delay = 1.0  # seconds
    jitter = 0.5      # seconds

    for attempt in range(max_retries + 1):
        try:
            json_results = call_knowledge_service(question, top_k=top_k)
            return parse_results(json_results)
        except Exception as e:
            if attempt == max_retries:
                print(f"[FAILED] question='{question}' after {attempt} retries. Error: {e}. Results: {json_results if 'json_results' in locals() else 'N/A'}")
                return []
            # Backoff with jitter
            delay = base_delay * (2 ** attempt) + random.uniform(0, jitter)
            print(f"[RETRY] attempt={attempt+1}/{max_retries} question='{question}' waiting {delay:.2f}s due to: {e}")
            time.sleep(delay)

def send_questions_to_knowledge_service(questions: list[str], top_k=5, max_workers=10, batch_size=10, batch_delay=4) -> list[str]:
    print("Retrieving knowledge service chunks...")
    results = [None] * len(questions)
    
    for batch_start in range(0, len(questions), batch_size):
        batch_end = min(batch_start + batch_size, len(questions))
        batch = questions[batch_start:batch_end]
        print(f"Processing batch {batch_start // batch_size + 1} (questions {batch_start + 1}-{batch_end} of {len(questions)})...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(process_single_question, question, top_k): batch_start + i
                for i, question in enumerate(batch)
            }

            for future in concurrent.futures.as_completed(future_to_index):
                idx = future_to_index[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    print(f"Failed to process question '{questions[idx]}': {e}")
                    results[idx] = []

        # Sleep between batches (skip after the last batch)
        if batch_end < len(questions):
            print(f"Sleeping {batch_delay}s before next batch...")
            time.sleep(batch_delay)

    # Combine all chunks in order
    #chunks = []
    #for result in results:
    #    if result:
    #        chunks.extend(result)

    return results
