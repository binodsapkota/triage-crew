from __future__ import annotations

from app.config import Settings
from app.llm.base import CrewLLM
from app.llm.demo import DemoLLM


def get_llm(settings: Settings) -> CrewLLM:
    """Pick the model behind the crew. Demo mode needs no key and is fully deterministic."""
    if settings.llm_provider == "openai":
        from app.llm.openai_llm import OpenAILLM

        return OpenAILLM(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=settings.openai_temperature,
        )
    return DemoLLM()
