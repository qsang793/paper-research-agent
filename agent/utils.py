"""
Utility functions for the agent system.

Includes retry logic, error handling helpers, and common decorators.
"""
import functools
import logging
import time
from typing import Callable, Optional, Tuple, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    fallback_value: Optional[T] = None,
) -> Callable:
    """
    Decorator for retry logic with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay between retries in seconds (default: 1.0)
        max_delay: Maximum delay between retries (default: 60.0)
        exponential_base: Base for exponential backoff (default: 2.0)
        exceptions: Tuple of exception types to catch and retry (default: all Exception)
        fallback_value: Value to return if all retries fail (default: None)
    
    Returns:
        Decorator function
    
    Example:
        @retry_with_backoff(max_retries=3, base_delay=2.0)
        def api_call():
            response = requests.get("https://api.example.com")
            return response.json()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    
                    # Last attempt - don't retry
                    if attempt == max_retries:
                        logger.error(
                            f"Function '{func.__name__}' failed after {max_retries + 1} attempts. "
                            f"Last error: {exc}"
                        )
                        break
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    logger.warning(
                        f"Function '{func.__name__}' failed (attempt {attempt + 1}/{max_retries + 1}): {exc}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    time.sleep(delay)
            
            # All retries exhausted
            if fallback_value is not None:
                logger.info(f"Returning fallback value for '{func.__name__}'")
                return fallback_value
            
            # Re-raise the last exception
            raise last_exception
        
        return wrapper
    return decorator


def safe_execute(
    func: Callable[..., T],
    *args,
    fallback_value: Optional[T] = None,
    log_error: bool = True,
    error_message: Optional[str] = None,
    **kwargs
) -> T:
    """
    Execute a function safely with error handling.
    
    Args:
        func: Function to execute
        *args: Positional arguments for the function
        fallback_value: Value to return if function fails (default: None)
        log_error: Whether to log errors (default: True)
        error_message: Custom error message (default: auto-generated)
        **kwargs: Keyword arguments for the function
    
    Returns:
        Function result or fallback_value on error
    
    Example:
        result = safe_execute(
            risky_function,
            arg1, arg2,
            fallback_value=[],
            error_message="Failed to process data"
        )
    """
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        if log_error:
            msg = error_message or f"Error executing '{func.__name__}': {exc}"
            logger.error(msg, exc_info=True)
        return fallback_value
