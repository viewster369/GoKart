import os
import logging
import time
from typing import List, Dict, Any, Optional
from openai import OpenAI, APIError, RateLimitError, APITimeoutError

logger = logging.getLogger(__name__)

class AIProvider:
    """
    Modular AI Provider for GroqCloud.
    Handles client initialization, retries, rate-limiting, and model selection.
    """
    
    def __init__(self):
        self.api_key = os.environ.get("GROQ_API_KEY", "")
        self.base_url = "https://api.groq.com/openai/v1"
        self.client = None
        self.available = False
        
        if self.api_key:
            try:
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=30.0  # Default timeout
                )
                self.available = True
                logger.info("GroqCloud AI Provider initialized successfully.")
            except Exception as e:
                logger.error(f"Failed to initialize GroqCloud client: {e}")
                self.available = False
        else:
            logger.warning("GROQ_API_KEY not found. AI features will be disabled.")

    def generate_comparison(
        self, 
        system_msg: str, 
        user_msg: str, 
        model: str = "qwen/qwen3-32b",
        temperature: float = 0.3,
        max_tokens: int = 1500,
        retries: int = 3
    ) -> Optional[str]:
        """
        Generates a product comparison using GroqCloud with retry logic.
        """
        if not self.available or not self.client:
            logger.error("AI Provider is not available.")
            return None

        last_error = None
        for attempt in range(retries):
            try:
                start_time = time.time()
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                duration = time.time() - start_time
                logger.info(f"Groq API call successful ({model}) in {duration:.2f}s")
                return response.choices[0].message.content.strip()

            except RateLimitError as e:
                last_error = f"Rate limit exceeded: {e}"
                wait_time = (attempt + 1) * 2  # Exponential backoff
                logger.warning(f"{last_error}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            except APITimeoutError as e:
                last_error = f"API Timeout: {e}"
                logger.warning(f"{last_error}. Retrying...")
            except APIError as e:
                last_error = f"Groq API Error: {e}"
                logger.error(last_error)
                if attempt == retries - 1:
                    break
                time.sleep(1)
            except Exception as e:
                last_error = f"Unexpected error in AI Provider: {e}"
                logger.exception(last_error)
                break
        
        logger.error(f"Failed to generate comparison after {retries} attempts. Last error: {last_error}")
        return None

    def get_fallback_model(self) -> str:
        """Returns the secondary/fallback model name."""
        return "llama-3.3-70b-versatile"
