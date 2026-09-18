"""Prompt templates live beside this file as .md so they can be reviewed and diffed like any other source."""

from functools import cache
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).parent


@cache
def load_prompt(name: str) -> Template:
    """`$placeholder` templates: braces are left alone, so JSON and prose in prompts need no escaping."""
    return Template((PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8"))
