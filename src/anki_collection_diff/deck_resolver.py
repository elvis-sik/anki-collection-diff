from __future__ import annotations

import os
import subprocess


class DeckResolutionError(RuntimeError):
    """Raised when a live deck name cannot be resolved."""


def resolve_deck_name(
    *,
    explicit_deck_name: str | None,
    env_var: str | None,
    agent: str | None,
    apkg_candidates: tuple[str, ...],
    live_deck_names: tuple[str, ...],
) -> str:
    if explicit_deck_name:
        return explicit_deck_name

    if env_var:
        env_value = os.environ.get(env_var)
        if env_value:
            return env_value

    exact = [name for name in apkg_candidates if name in set(live_deck_names)]
    if len(exact) == 1:
        return exact[0]

    if agent:
        return _resolve_with_agent(agent, apkg_candidates, live_deck_names)

    raise DeckResolutionError(
        "Could not infer a single live deck. Pass --deck-name, set the deck env var, "
        "or use --deck-agent. APKG candidates: "
        + ", ".join(apkg_candidates)
    )


def _resolve_with_agent(
    agent: str,
    apkg_candidates: tuple[str, ...],
    live_deck_names: tuple[str, ...],
) -> str:
    prompt = (
        "Choose the one live Anki deck name that best matches this APKG. "
        "Return only the deck name, with no commentary.\n\n"
        "APKG candidate deck names:\n"
        + "\n".join(f"- {name}" for name in apkg_candidates)
        + "\n\nLive deck names:\n"
        + "\n".join(f"- {name}" for name in live_deck_names)
    )
    command = _agent_command(agent, prompt)
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=True, timeout=120)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise DeckResolutionError(f"Deck resolver agent failed: {agent}") from exc

    answer = result.stdout.strip().splitlines()[0].strip()
    if answer not in live_deck_names:
        raise DeckResolutionError(f"Deck resolver returned an unknown live deck: {answer}")
    return answer


def _agent_command(agent: str, prompt: str) -> list[str]:
    if agent == "claude":
        return ["claude", "-p", prompt]
    if agent == "codex":
        return ["codex", "exec", prompt]
    raise DeckResolutionError(f"Unsupported deck resolver agent: {agent}")
