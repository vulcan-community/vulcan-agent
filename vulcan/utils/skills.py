"""Shared helpers for loading Vulcan skills from disk.

A **skill** is a subdirectory of `skills_dir/` that contains at least a
`SKILL.md` file. Each runtime decides how to expose skills to its
backend:

- Claude Code uses its native Skill tool — SDK discovers skills under
  `<cwd>/.claude/skills/`, injects only an index into the system
  prompt, and lazy-loads the full `SKILL.md` body when the agent calls
  the Skill tool. No loading happens here.
- Codex has no native skill concept but can read files via its shell
  tool. We inject a short catalog (name + description) and grant it
  read access to `skills_dir` via `additional_directories`, letting
  the agent `cat` the full body on demand. Use `render_skills_catalog`.
- Base OpenAI has no tools at all, so there is no "lazy" option: it
  gets the full SKILL.md content injected into the system prompt via
  `render_skills_prompt`. Cost scales with skill count.

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


def parse_skill_description(skill_md_text: str) -> str:
    """Extract `description:` from a SKILL.md's YAML frontmatter.

    Falls back to the first non-blank, non-heading, non-`---` line of
    the body. Returns empty string if nothing usable is found.
    """
    lines = skill_md_text.splitlines()
    if lines and lines[0].strip() == "---":
        for line in lines[1:]:
            if line.strip() == "---":
                break
            lower = line.strip().lower()
            if lower.startswith("description:"):
                return line.split(":", 1)[1].strip()
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and not s.startswith("---"):
            return s
    return ""


def render_skills_prompt(skills: list[tuple[str, str]]) -> str:
    """Render the **full** catalog: every SKILL.md body inlined. Used by
    runtimes that can't lazy-load (base-openai has no tools). Empty if
    no skills.
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


def render_skills_catalog(
    skills: list[tuple[str, str]], base_dir_hint: str = ""
) -> str:
    """Render the **short** catalog: one line per skill with only the
    frontmatter description. Used by runtimes that can fetch the full
    body on demand (Codex via its shell tool reading from
    `additional_directories`). Empty if no skills.
    """
    if not skills:
        return ""
    lines = ["# Available skills"]
    if base_dir_hint:
        lines.append(
            f"Full content lives at `{base_dir_hint}/<name>/SKILL.md`. "
            "Read the file when the user's request matches a skill's "
            "description below."
        )
    lines.append("")
    for name, text in skills:
        desc = parse_skill_description(text) or "(no description)"
        lines.append(f"- **{name}** — {desc}")
    lines.append("")
    return "\n".join(lines)
