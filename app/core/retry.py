import time
import random
import logging

logger = logging.getLogger(__name__)

def retry_with_backoff(func, *args, max_retries=5, initial_backoff=1.0, **kwargs):
    """
    Retry a function with exponential backoff and random jitter.
    Useful for handling Google Gemini API rate limits (HTTP 429) or network hiccups.
    """
    backoff = initial_backoff
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            is_last_attempt = attempt == max_retries - 1
            if is_last_attempt:
                logger.error(f"Function {func.__name__} failed after {max_retries} attempts: {str(e)}")
                raise e
            
            # Exponential backoff + random jitter/noise add karo
            sleep_time = backoff + random.uniform(0.1, 0.5)
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries} failed for {func.__name__}: {str(e)}. "
                f"Retrying in {sleep_time:.2f} seconds..."
            )
            time.sleep(sleep_time)
            backoff *= 2.0
