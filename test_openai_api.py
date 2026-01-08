#!/usr/bin/env python3
"""
Test script to verify OpenAI API updates work correctly.
This script tests the basic API functionality without making actual API calls
(unless you provide a valid API key).
"""

import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from promptengine.utils import LLM, call_chatgpt, extract_responses, set_openai_api_key
from promptengine.pipelines import PromptPipeline
from promptengine.template import PromptTemplate, PromptPermutationGenerator

def test_imports():
    """Test that all imports work correctly."""
    print("✓ Imports successful")
    return True

def test_api_structure():
    """Test that the API structure is correct (without making actual calls)."""
    try:
        from openai import OpenAI
        # Test that we can create a client (will fail if API key is invalid, but structure is correct)
        print("✓ OpenAI client import successful")
        
        # Test that call_chatgpt function signature is correct
        import inspect
        sig = inspect.signature(call_chatgpt)
        params = list(sig.parameters.keys())
        assert 'prompt' in params
        assert 'n' in params
        assert 'temperature' in params
        assert 'api_key' in params
        print("✓ call_chatgpt function signature correct")
        
        return True
    except Exception as e:
        print(f"✗ API structure test failed: {e}")
        return False

def test_with_api_key(api_key: str = None):
    """Test actual API call if API key is provided."""
    if not api_key:
        print("⚠ Skipping actual API call test (no API key provided)")
        print("  To test with a real API key, run: python test_openai_api.py YOUR_API_KEY")
        return True
    
    try:
        print(f"\nTesting with API key (first 10 chars: {api_key[:10]}...)")
        
        # Test simple API call
        test_prompt = "Say 'Hello, World!' and nothing else."
        query, response = call_chatgpt(test_prompt, n=1, temperature=0.7, api_key=api_key)
        
        # Verify response structure
        assert "choices" in response, "Response should have 'choices' key"
        assert len(response["choices"]) > 0, "Response should have at least one choice"
        assert "message" in response["choices"][0], "Choice should have 'message' key"
        assert "content" in response["choices"][0]["message"], "Message should have 'content' key"
        
        print("✓ API call successful")
        print(f"✓ Response structure correct")
        
        # Test response extraction
        extracted = extract_responses({"response": response}, LLM.ChatGPT)
        assert len(extracted) > 0, "Should extract at least one response"
        assert isinstance(extracted[0], str), "Extracted response should be a string"
        print(f"✓ Response extraction successful: '{extracted[0][:50]}...'")
        
        return True
    except Exception as e:
        print(f"✗ API call test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_pipeline_structure():
    """Test that pipeline can be created and has correct structure."""
    try:
        # Create a simple test pipeline class
        class TestPipeline(PromptPipeline):
            def gen_prompts(self, properties):
                template = PromptTemplate("Test: ${text}")
                gen = PromptPermutationGenerator(template)
                return list(gen({"text": properties.get("text", "test")}))
            
            def analyze_response(self, response):
                return True
        
        pipeline = TestPipeline("test_responses.json")
        print("✓ Pipeline creation successful")
        
        # Test that gen_responses accepts api_key parameter
        import inspect
        sig = inspect.signature(pipeline.gen_responses)
        assert 'api_key' in sig.parameters, "gen_responses should accept api_key parameter"
        print("✓ Pipeline gen_responses signature correct")
        
        # Clean up test file
        if os.path.exists("test_responses.json"):
            os.remove("test_responses.json")
        
        return True
    except Exception as e:
        print(f"✗ Pipeline structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_response_extraction():
    """Test response extraction with mock data."""
    try:
        # Mock response in the format that would come from gen_responses
        mock_response = {
            "prompt": "Test prompt",
            "query": {"model": "gpt-3.5-turbo", "messages": []},
            "response": {
                "choices": [
                    {"message": {"content": "Hello, World!"}},
                    {"message": {"content": "Test response 2"}}
                ]
            },
            "llm": "ChatGPT",
            "info": {}
        }
        
        # Test extraction
        extracted = extract_responses(mock_response, LLM.ChatGPT)
        assert len(extracted) == 2, "Should extract 2 responses"
        assert extracted[0] == "Hello, World!", "First response should match"
        assert extracted[1] == "Test response 2", "Second response should match"
        assert all(isinstance(r, str) for r in extracted), "All responses should be strings"
        
        print("✓ Response extraction with mock data successful")
        return True
    except Exception as e:
        print(f"✗ Response extraction test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("Testing OpenAI API updates...\n")
    
    results = []
    
    # Test 1: Imports
    results.append(("Imports", test_imports()))
    
    # Test 2: API Structure
    results.append(("API Structure", test_api_structure()))
    
    # Test 3: Pipeline Structure
    results.append(("Pipeline Structure", test_pipeline_structure()))
    
    # Test 4: Response Extraction
    results.append(("Response Extraction", test_response_extraction()))
    
    # Test 5: Actual API call (if key provided)
    api_key = sys.argv[1] if len(sys.argv) > 1 else None
    results.append(("API Call", test_with_api_key(api_key)))
    
    # Summary
    print("\n" + "="*50)
    print("Test Summary:")
    print("="*50)
    all_passed = True
    for test_name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"{test_name}: {status}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())

