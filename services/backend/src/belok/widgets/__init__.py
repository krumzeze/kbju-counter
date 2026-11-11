from functools import cache
from importlib.resources import files


@cache
def html(name: str) -> str:
    source = files(__package__).joinpath(f"{name}.html").read_text("utf-8")
    return "\n".join(line.strip() for line in source.splitlines() if line.strip())
