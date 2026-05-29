import os
import time
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# Ordered list of models to try in case of quota limits
MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

def get_api_keys() -> list[str]:
    """Retrieve all available Gemini API keys from environment variables."""
    keys = []
    # Check standard GOOGLE_API_KEY
    k1 = os.getenv("GOOGLE_API_KEY")
    if k1:
        keys.append(k1.strip())
    
    # Check potential backup keys (GOOGLE_API_KEY2, GOOGLE_API_KEY_2, GOOGLE_API_KEY3, etc.)
    for i in range(2, 6):
        for prefix in [f"GOOGLE_API_KEY_{i}", f"GOOGLE_API_KEY{i}"]:
            ki = os.getenv(prefix)
            if ki:
                keys.append(ki.strip())
    
    # Ensure we don't have duplicates
    unique_keys = []
    for k in keys:
        if k not in unique_keys:
            unique_keys.append(k)
            
    return unique_keys

def invoke_llm_with_fallback(prompt_messages, temperature=0.1) -> str:
    """
    Invokes Gemini with automatic model-rotation and API-key-rotation
    to bypass 429 RESOURCE_EXHAUSTED free tier daily limits.
    """
    keys = get_api_keys()
    if not keys:
        raise ValueError("No GOOGLE_API_KEY found in environment variables!")

    last_error = None

    # Rotate through all available API keys
    for key_idx, key in enumerate(keys):
        # Rotate through all available models
        for model in MODELS:
            try:
                print(f"🤖 Attempting LLM call (Model: {model}, Key Index: {key_idx + 1}/{len(keys)})...")
                
                # Initialize client with current key and model
                llm_instance = ChatGoogleGenerativeAI(
                    model=model,
                    temperature=temperature,
                    google_api_key=key
                )
                
                # Call LLM
                response = llm_instance.invoke(prompt_messages)
                content = response.content.strip()
                
                print(f"✅ Success with Model: {model} using Key Index {key_idx + 1}!")
                return content
                
            except Exception as e:
                err_str = str(e)
                print(f"⚠️ Failed with Model: {model} using Key Index {key_idx + 1}: {err_str}")
                last_error = e
                
                # Sleep briefly before trying next model
                time.sleep(1)
                continue

    # If everything fails, raise the last exception
    raise last_error or Exception("Failed to invoke Gemini LLM on all models and keys.")

class GeminiResponse:
    """Mock response object to mimic LangChain's response interface."""
    def __init__(self, content: str):
        self.content = content

class GeminiFallbackClient:
    """Mock LLM client to mimic LangChain's ChatGoogleGenerativeAI with fallback protection."""
    def __init__(self, temperature=0.1):
        self.temperature = temperature

    def invoke(self, prompt_messages) -> GeminiResponse:
        content = invoke_llm_with_fallback(prompt_messages, self.temperature)
        return GeminiResponse(content)

# Export a default instance for easy backwards compatibility
llm = GeminiFallbackClient(temperature=0.1)
