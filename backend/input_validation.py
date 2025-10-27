"""
Input Validation and Sanitization

Prevents security issues like:
- Prompt injection attacks
- SQL injection (not applicable but defensive)
- XSS attacks
- DoS via overly long inputs
- Special character exploits

Usage:
    from input_validation import sanitize_query, validate_query_length

    clean_query = sanitize_query(user_input)
    validate_query_length(clean_query)
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Security configuration
MAX_QUERY_LENGTH = 1000  # Maximum characters allowed in query
MAX_WORD_COUNT = 100  # Maximum words allowed in query
MIN_QUERY_LENGTH = 1  # Minimum characters required

# Patterns to detect potential attacks
SUSPICIOUS_PATTERNS = [
    r"<script[^>]*>",  # Script tags
    r"javascript:",  # JavaScript protocol
    r"on\w+\s*=",  # Event handlers (onclick, onload, etc.)
    r"eval\s*\(",  # eval() calls
    r"exec\s*\(",  # exec() calls
    r"__import__",  # Python imports
    r"subprocess",  # Python subprocess
    r"DROP\s+TABLE",  # SQL injection
    r"DELETE\s+FROM",  # SQL injection
    r"INSERT\s+INTO",  # SQL injection
    r"UPDATE\s+.*SET",  # SQL injection
]

# Prompt injection indicators
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|above)",
    r"forget\s+(all\s+)?(previous|prior|above)",
    r"you\s+are\s+now",
    r"new\s+instructions",
    r"system\s*:\s*",
    r"assistant\s*:\s*",
    r"###\s*Instruction",
]


class ValidationError(Exception):
    """Raised when input validation fails"""
    pass


class SuspiciousInputError(ValidationError):
    """Raised when potentially malicious input is detected"""
    pass


def sanitize_query(query: str, strict: bool = False) -> str:
    """
    Sanitize user query to prevent injection attacks

    Args:
        query: Raw user input
        strict: If True, removes more aggressively

    Returns:
        Sanitized query string

    Raises:
        ValidationError: If query is invalid
        SuspiciousInputError: If malicious patterns detected
    """
    if not query:
        raise ValidationError("Query cannot be empty")

    # Strip whitespace
    query = query.strip()

    # Check minimum length
    if len(query) < MIN_QUERY_LENGTH:
        raise ValidationError(f"Query must be at least {MIN_QUERY_LENGTH} character(s)")

    # Check maximum length BEFORE processing
    if len(query) > MAX_QUERY_LENGTH:
        logger.warning(f"Query truncated from {len(query)} to {MAX_QUERY_LENGTH} characters")
        query = query[:MAX_QUERY_LENGTH]

    # Detect suspicious patterns (before sanitization to catch attacks)
    for pattern in SUSPICIOUS_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            logger.error(f"Suspicious pattern detected in query: {pattern}")
            raise SuspiciousInputError(
                "Query contains suspicious patterns. "
                "Please rephrase your search without special characters or code."
            )

    # Detect prompt injection attempts
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            logger.warning(f"Possible prompt injection detected: {pattern}")
            # Don't raise error, just log and sanitize
            # (Some legitimate queries might match these patterns)

    # Normalize whitespace (multiple spaces → single space)
    query = re.sub(r'\s+', ' ', query)

    if strict:
        # Strict mode: Only allow alphanumeric, spaces, and basic punctuation
        query = re.sub(r'[^a-zA-Z0-9\s\-.,?!\'\"&()]', '', query)
    else:
        # Normal mode: Remove potentially dangerous characters
        # Keep most punctuation for natural language queries
        query = re.sub(r'[<>{}[\]\\|`~^]', '', query)

    # Check word count
    word_count = len(query.split())
    if word_count > MAX_WORD_COUNT:
        logger.warning(f"Query has {word_count} words, truncating to {MAX_WORD_COUNT}")
        query = ' '.join(query.split()[:MAX_WORD_COUNT])

    # Final length check
    if len(query) > MAX_QUERY_LENGTH:
        query = query[:MAX_QUERY_LENGTH]

    return query


def validate_query_length(query: str) -> None:
    """
    Validate query length constraints

    Args:
        query: Query to validate

    Raises:
        ValidationError: If query length is invalid
    """
    if len(query) > MAX_QUERY_LENGTH:
        raise ValidationError(
            f"Query too long. Maximum {MAX_QUERY_LENGTH} characters allowed, "
            f"got {len(query)} characters."
        )

    if len(query) < MIN_QUERY_LENGTH:
        raise ValidationError(
            f"Query too short. Minimum {MIN_QUERY_LENGTH} character(s) required."
        )


def validate_top_k(top_k: int) -> None:
    """
    Validate top_k parameter

    Args:
        top_k: Number of results requested

    Raises:
        ValidationError: If top_k is invalid
    """
    if top_k < 1:
        raise ValidationError("top_k must be at least 1")

    if top_k > 20:
        raise ValidationError("top_k cannot exceed 20 (resource protection)")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal attacks

    Args:
        filename: Raw filename

    Returns:
        Sanitized filename
    """
    # Remove path separators
    filename = filename.replace('/', '').replace('\\', '')

    # Remove potentially dangerous patterns
    filename = re.sub(r'\.\.+', '.', filename)  # Multiple dots
    filename = re.sub(r'[<>:"|?*]', '', filename)  # Windows illegal chars

    return filename


def detect_prompt_injection(text: str) -> tuple[bool, Optional[str]]:
    """
    Detect potential prompt injection attempts

    Args:
        text: Text to analyze

    Returns:
        (is_suspicious, matched_pattern)
    """
    for pattern in PROMPT_INJECTION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return True, pattern

    return False, None


def safe_truncate(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Safely truncate text to maximum length

    Args:
        text: Text to truncate
        max_length: Maximum length (including suffix)
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    # Account for suffix length
    actual_max = max_length - len(suffix)

    if actual_max <= 0:
        return text[:max_length]

    return text[:actual_max] + suffix


# Validation presets
def validate_search_request(query: str, top_k: int) -> tuple[str, int]:
    """
    Validate and sanitize a complete search request

    Args:
        query: User query
        top_k: Number of results

    Returns:
        (sanitized_query, validated_top_k)

    Raises:
        ValidationError: If validation fails
    """
    # Sanitize query
    clean_query = sanitize_query(query, strict=False)

    # Validate parameters
    validate_query_length(clean_query)
    validate_top_k(top_k)

    logger.info(
        f"Validated search request: query_len={len(clean_query)}, "
        f"word_count={len(clean_query.split())}, top_k={top_k}"
    )

    return clean_query, top_k
