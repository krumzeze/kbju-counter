# USD per million input and output tokens.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
}
CACHE_WRITE = 1.25
CACHE_READ = 0.1


def cost(model: str, usage: object) -> float | None:
    prices = PRICES.get(model)
    if prices is None:
        return None
    written = getattr(usage, "cache_creation_input_tokens", None) or 0
    read = getattr(usage, "cache_read_input_tokens", None) or 0
    tokens_in = usage.input_tokens + written * CACHE_WRITE + read * CACHE_READ
    return (tokens_in * prices[0] + usage.output_tokens * prices[1]) / 1_000_000


def prompt_tokens(usage: object) -> int:
    written = getattr(usage, "cache_creation_input_tokens", None) or 0
    read = getattr(usage, "cache_read_input_tokens", None) or 0
    return usage.input_tokens + written + read
