import json
import os
import time
import datetime 
from openai import AzureOpenAI

def write_jsonl(system_prompt: str, custom_id: str, deployment_name: str, user_content: str, output_file_path):
    """Write the contents to a JSONL file with the specified format."""

    with open(output_file_path, 'a') as output_file:
        json_line = {
            "custom_id": custom_id,
            "method": "POST",
            "url": "/chat/completions",
            "body": {
                "model": deployment_name,
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_content
                    }
                ]
            }
        }
        output_file.write(json.dumps(json_line) + '\n')

def create_batch_client() -> AzureOpenAI:
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_KEY"), 
        api_version="2025-04-01-preview"
    )
    return client

def upload_batch_file(client: AzureOpenAI, file_path: str) -> str:
    # Upload a file with a purpose of "batch"
    file = client.files.create(
        file=open(file_path, "rb"),
        purpose="batch",
        extra_body={"expires_after": {"seconds": 1209600, "anchor": "created_at"}}  # Optional you can set to a number between 1209600-2592000. This is equivalent to 14-30 days
    )

    return file.id

def create_batch_job(client: AzureOpenAI, file_id: str) -> str:
    # Submit a batch job with the file
    batch_response = client.batches.create(
        input_file_id=file_id,
        endpoint="/chat/completions",
        completion_window="24h",
        extra_body={"output_expires_after": {"seconds": 1209600, "anchor": "created_at"}}  # Optional you can set to a number between 1209600-2592000. This is equivalent to 14-30 days
    )

    return batch_response.id

def track_batch_status(client: AzureOpenAI, batch_id: str):
    status = "validating"
    while status not in ("completed", "failed", "cancelled"):
        batch_response = client.batches.retrieve(batch_id)
        status = batch_response.status
        print(f"{datetime.datetime.now()} Batch Id: {batch_id},  Status: {status}")
        if status not in ("completed", "failed", "cancelled"):
            time.sleep(120)

    return batch_response

def process_batch_response(client: AzureOpenAI, batch_response, batch_id: str) -> str:
    """Process the batch response and print the results."""
    message = ""
    if batch_response.status == "failed":
        print(f"Batch {batch_id} failed with errors.")
        for error in batch_response.errors.data:
            print(f"Error code {error.code} Message {error.message}")
            return ""
    elif batch_response.status == "cancelled":
        print(f"Batch {batch_id} was cancelled.")
        return ""
    elif batch_response.status == "completed":
        print(f"Batch {batch_id} completed successfully.")
        return batch_response.output_file_id

def extract_batch_results(client: AzureOpenAI, output_file_id: str) -> dict:
    """Retrieve and print the results from the batch output file."""
    results = {}
    if output_file_id:
        file_response = client.files.content(output_file_id)
        raw_responses = file_response.text.strip().split('\n')  

    for raw_response in raw_responses:  
        data = json.loads(raw_response)  
        batch_custom_id = data.get("custom_id")
        message = data.get("response", {}).get("body", {}).get("choices", [{}])[0].get("message", {}).get("content")
        if batch_custom_id and message is not None:
            results[batch_custom_id] = message
        
    return results

def send_batch(batch_file_path: str) -> str:
    """Main function to create and process a batch job."""
    client = create_batch_client()
    
    # Upload the batch file
    file_id = upload_batch_file(client, batch_file_path)

    # Create a batch job
    batch_id = create_batch_job(client, file_id)

    return batch_id

def get_batch_results(batch_id: str) -> dict:
    client = create_batch_client()

    # Track the batch job status
    batch_response = track_batch_status(client, batch_id)

    # Process the batch response
    output_file_id = process_batch_response(client, batch_response, batch_id)

    # Retrieve and print the results
    results = extract_batch_results(client, output_file_id)
    
    return results

def create_batch_file_path(base_dir: str, scenario: str, timestamp: str) -> str:
    """Main function to read files and write to a JSONL file."""

    output_file_path = ""

    #base_dir = os.path.dirname(os.path.abspath(__file__))
    folder_path = os.path.join(base_dir, "data", "batch")
    os.makedirs(folder_path, exist_ok=True)

    output_file_path = os.path.join(folder_path, f"{scenario}_batch_{timestamp}.jsonl")

    return output_file_path  