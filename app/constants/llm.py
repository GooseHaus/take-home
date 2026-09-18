"""LLM constants (D6)."""

# Articles at or above this relevance count as cited by an explanation
CITATION_MIN_RELEVANCE = 0.5

# Candidate articles shown to the model per movement; keeps prompts small and cost predictable
MAX_ARTICLES_IN_PROMPT = 18

LLM_MAX_RETRIES = 2
LLM_TIMEOUT_SECONDS = 60
