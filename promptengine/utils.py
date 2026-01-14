from typing import Dict, Tuple, List, Union, Optional
from enum import Enum
from openai import OpenAI
import json

""" Supported LLM coding assistants """
class LLM(Enum):
    ChatGPT = 0

# Global client instance (will be initialized with API key when needed)
_client: Optional[OpenAI] = None

def set_openai_api_key(api_key: str):
    """Set the OpenAI API key and initialize the client."""
    global _client
    _client = OpenAI(api_key=api_key)

def get_openai_client() -> OpenAI:
    """Get the OpenAI client instance. Raises error if not initialized."""
    global _client
    if _client is None:
        raise ValueError("OpenAI API key not set. Call set_openai_api_key() first.")
    return _client

def call_chatgpt(prompt: str, n: int = 1, temperature: float = 1.0, api_key: Optional[str] = None, system_message: str = "You are a helpful assistant.") -> Tuple[Dict, Dict]:
    """
    Call ChatGPT API. If api_key is provided, uses it; otherwise uses the global client.
    """
    # Validate and clean API key if provided
    if api_key:
        api_key = api_key.strip()
        if not api_key:
            raise ValueError("API key cannot be empty. Please provide a valid OpenAI API key.")
        client = OpenAI(api_key=api_key)
    else:
        # If no API key provided, try to use global client
        try:
            client = get_openai_client()
        except ValueError:
            # Global client not initialized, and no API key provided
            raise ValueError("No API key provided. Please provide an OpenAI API key either as a parameter or by calling set_openai_api_key().")
    
    query = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt},
        ],
        "n": n,
        "temperature": temperature,
    }
    
    # Use new API format
    response = client.chat.completions.create(**query)
    
    # Convert response to dict format for backward compatibility
    response_dict = {
        "choices": [
            {
                "message": {
                    "content": choice.message.content
                }
            }
            for choice in response.choices
        ]
    }
    
    return query, response_dict

def _extract_chatgpt_responses(response: dict) -> List[str]:
    """
        Extracts the text part of a response JSON from ChatGPT. If there are more
        than 1 response (e.g., asking the LLM to generate multiple responses), 
        this produces a list of all returned responses.
    """
    # Handle both old format (response["response"]["choices"]) and new format (response["choices"])
    if "response" in response:
        choices = response["response"]["choices"]
    else:
        choices = response["choices"]
    return [
        c["message"]["content"]
        for i, c in enumerate(choices)
    ]

def extract_responses(response: dict, llm: LLM) -> List[str]:
    """
        Given a LLM and a response object from its API, extract the
        text response(s) part of the response object.
    """
    if llm is LLM.ChatGPT or llm == LLM.ChatGPT.name:
        return _extract_chatgpt_responses(response)
    else:
        raise ValueError(f"LLM {llm} is unsupported.")

def is_valid_filepath(filepath: str) -> bool:
    try:
        with open(filepath, 'r'):
            pass
    except IOError:
        try:
            # Create the file if it doesn't exist, and write an empty json string to it
            with open(filepath, 'w+') as f:
                f.write("{}")
                pass
        except IOError:
            return False
    return True

def is_valid_json(json_dict: dict) -> bool:
    if isinstance(json_dict, dict):
        try:
            json.dumps(json_dict)
            return True
        except:
            pass
    return False
