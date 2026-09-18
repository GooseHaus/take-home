"""Chat constants (D8)."""

# Model -> tools -> model rounds before the model is made to answer with what it has
MAX_TOOL_ROUNDS = 6

# Prior user/assistant messages replayed into a new turn
HISTORY_MESSAGES = 12

MAX_MESSAGE_CHARS = 4000

# Tool results are model context, so they're kept compact
TOOL_DEFAULT_MOVEMENTS = 10
TOOL_MAX_MOVEMENTS = 40
TOOL_ARTICLES_PER_MOVEMENT = 3
TOOL_SEARCH_DEFAULT = 8
TOOL_SEARCH_MAX = 20
TOOL_SNIPPET_CHARS = 280
