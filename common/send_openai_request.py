import os
from openai import AzureOpenAI
from typing import Optional

def create_client() -> AzureOpenAI:
    """Create and return an AzureOpenAI client."""
    client = AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_key=os.getenv("AZURE_OPENAI_KEY"), 
        api_version="2025-04-01-preview"
    )
    return client

def send_response_request(
    deployment_name: str, 
    prompt: str, 
    input_text: str, 
    effort: str,
    client: Optional[AzureOpenAI] = None
) -> str:
    """Send a GPT 5 response request and return the response content."""
    if client is None:
        client = create_client()
    
    response = client.responses.create(
        model=deployment_name,
        instructions=prompt,
        input=input_text,
        reasoning={"effort": effort}
    )
    return response.output_text
