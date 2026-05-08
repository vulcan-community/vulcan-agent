"""Shared helpers for loading Vulcan skills from disk.

A **skill** is a subdirectory of `skills_dir/` that contains at least a
`SKILL.md` file. Each runtime decides how to expose skills to its
backend:

- Claude Code uses its native skill mechanism (cwd + setting_sources),
  which discovers skills lazily when the agent needs them. No loading
  happens here — see `ClaudeCodeRuntime.invoke`.
- Codex and base-openai have no native skill concept, so they inject the
  full skill catalog into the prompt eagerly. Those runtimes call
  `load_skills()` / `render_skills_prompt()` below.

Keep this module independent of any runtime SDK — it's pure filesystem.
"""

from pathlib import Path


def load_skills(skills_dir: Path | None) -> list[tuple[str, str]]:
    """Return `[(skill_name, skill_md_text), ...]` for every subdirectory
    of `skills_dir` that contains a readable `SKILL.md`. Skills with no
    `SKILL.md` (or unreadable bytes) are skipped silently.
    """
    if skills_dir is None or not skills_dir.exists():
        return []
    out: list[tuple[str, str]] = []
    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.exists():
            continue
        try:
            text = skill_md.read_text()
        except OSError:
            continue
        out.append((entry.name, text))
    return out


def render_skills_prompt(skills: list[tuple[str, str]]) -> str:
    """Wrap loaded skills into a single markdown section suitable for
    prepending to a persona/system prompt. Returns empty string if there
    are no skills.
    """
    if not skills:
        return ""
    sections = ["# Available skills", ""]
    for name, text in skills:
        sections.append(f"## Skill: {name}")
        sections.append("")
        sections.append(text.strip())
        sections.append("")
    return "\n".join(sections).rstrip() + "\n"
