"""LLM constants (D6)."""

# Articles at or above this relevance count as cited by an explanation
CITATION_MIN_RELEVANCE = 0.5

# Candidate articles shown to the model per movement; keeps prompts small and cost predictable
MAX_ARTICLES_IN_PROMPT = 18

LLM_MAX_RETRIES = 2

# Stored verdicts should not change between runs on the same evidence, so structured calls ask for the least random
# sampling the API offers. This narrows the variation; it does not remove it (D24).
STRUCTURED_SAMPLING = {"temperature": 0, "seed": 7}
LLM_TIMEOUT_SECONDS = 60
