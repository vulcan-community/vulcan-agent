"""`/skill` command: manage locally-installed agent skills and browse the
remote skills registry.

Subcommands:
  list                  — show skills under the gateway's skills_dir.
  remove <name>         — delete a local skill directory.
  search <query>        — query the skills registry by keyword.
  add <slug>            — download and extract a skill from the registry.
  show <slug>           — show registry detail for one skill.
"""

import json
import os
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from typing import TYPE_CHECKING, Any

from openai.types.chat import ChatCompletion

from ..base_command import BaseCommand

if TYPE_CHECKING:
    from ...gateway import Gateway


_REGISTRY_BASE = "https://skills.volces.com/api/v1"
_HTTP_TIMEOUT = 10.0
_SUMMARY_MAX = 100


class SkillCommand(BaseCommand):
    def __init__(self, gateway: "Gateway") -> None:
        super().__init__(
            command="skill",
            description=(
                "Manage agent skills — subcommands: list / remove <name> /"
                " search <query> / add <slug> / show <slug>:"
                " /skill <subcommand> [args]"
            ),
        )
        self._gateway = gateway

    def exec(
        self, args: list[str], channel_id: str, conversation_id: str
    ) -> ChatCompletion:
        del channel_id, conversation_id
        if not args:
            return self._reply(self._usage())
        verb = args[0]
        rest = args[1:]
        if verb == "list":
            return self._list(rest)
        if verb == "remove":
            return self._remove(rest)
        if verb == "search":
            return self._search(rest)
        if verb == "add":
            return self._add(rest)
        if verb == "show":
            return self._show(rest)
        return self._reply(f"Unknown subcommand '{verb}'.\n{self._usage()}")

    @staticmethod
    def _usage() -> str:
        return (
            "Usage: /skill <subcommand> [args]\n"
            "  list                 List installed skills.\n"
            "  remove <name>        Remove a local skill.\n"
            "  search <query>       Search the skills registry.\n"
            "  add <slug>           Install a skill from the registry.\n"
            "  show <slug>          Show skill detail from the registry."
        )

    def _skills_dir(self):
        return self._gateway.skills_dir

    # ---------- subcommands ----------

    def _list(self, args: list[str]) -> ChatCompletion:
        del args
        try:
            from ....utils.skills import load_skills

            skills_dir = self._skills_dir()
            skills = load_skills(skills_dir)
            if not skills:
                return self._reply(f"No skills installed at {skills_dir}.")
            lines = [f"Skills ({len(skills)} installed at {skills_dir}):"]
            for name, md in skills:
                desc = _first_description_line(md)
                lines.append(f"  {name}  {desc}")
            return self._reply("\n".join(lines))
        except Exception as e:
            return self._reply(f"/skill list failed: {type(e).__name__}: {e}")

    def _remove(self, args: list[str]) -> ChatCompletion:
        try:
            if not args:
                return self._reply("Usage: /skill remove <name>.")
            name = args[0]
            skills_dir = self._skills_dir()
            target = skills_dir / name
            if not target.exists() or not target.is_dir():
                return self._reply(f"Skill '{name}' not installed.")
            shutil.rmtree(target)
            return self._reply(f"Removed skill '{name}' from {skills_dir}.")
        except Exception as e:
            return self._reply(f"/skill remove failed: {type(e).__name__}: {e}")

    def _search(self, args: list[str]) -> ChatCompletion:
        try:
            if not args:
                return self._reply("Usage: /skill search <query>.")
            query = " ".join(args)
            results = _registry_search(query, limit=20)
            if not results:
                return self._reply(f"No results for '{query}'.")
            lines = [f"Search results for '{query}' ({len(results)}):"]
            lines.extend(_format_search_rows(results))
            return self._reply("\n".join(lines))
        except Exception as e:
            return self._reply(f"/skill search failed: {type(e).__name__}: {e}")

    def _add(self, args: list[str]) -> ChatCompletion:
        try:
            if not args:
                return self._reply("Usage: /skill add <slug>.")
            slug = args[0]
            skills_dir = self._skills_dir()
            target = skills_dir / slug
            if target.exists():
                return self._reply(
                    f"Skill '{slug}' already installed."
                    f" Run /skill remove {slug} first to replace."
                )
            detail = _registry_get_detail(slug)
            if detail is None:
                return self._reply(f"Skill '{slug}' not found in registry.")
            version = (detail.get("latestVersion") or {}).get("version") or ""
            if not version:
                return self._reply(f"Skill '{slug}' has no resolvable version.")
            zip_bytes = _registry_download(slug, version)
            _extract_zip_into(zip_bytes, target)
            return self._reply(
                f"Installed skill '{slug}' v{version} at {skills_dir}/{slug}/."
            )
        except Exception as e:
            return self._reply(f"/skill add failed: {type(e).__name__}: {e}")

    def _show(self, args: list[str]) -> ChatCompletion:
        try:
            if not args:
                return self._reply("Usage: /skill show <slug>.")
            slug = args[0]
            detail = _registry_get_detail(slug)
            if detail is None:
                similar = _registry_search(slug, limit=5)
                if not similar:
                    return self._reply(
                        f"Skill '{slug}' not found. No similar skills."
                    )
                lines = [f"Skill '{slug}' not found. Similar skills:"]
                lines.extend(_format_search_rows(similar))
                return self._reply("\n".join(lines))
            return self._reply(_format_show(slug, detail))
        except Exception as e:
            return self._reply(f"/skill show failed: {type(e).__name__}: {e}")


# ---------- helpers ----------


def _first_description_line(skill_md: str) -> str:
    """Pick a short description line from a SKILL.md body. Skips blank
    lines and the leading `# Title` heading if present.
    """
    for raw in skill_md.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        return line
    # Fallback: the first non-empty line, even if it was a heading.
    for raw in skill_md.splitlines():
        line = raw.strip()
        if line:
            return line.lstrip("#").strip()
    return ""


def _truncate(text: str, limit: int) -> str:
    text = text.strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _format_search_rows(results: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for idx, item in enumerate(results):
        if idx > 0:
            lines.append("")  # blank line separator between items
        slug = item.get("slug", "")
        version = item.get("version", "")
        display = item.get("displayName", "")
        summary = _truncate(item.get("summary", "") or "", _SUMMARY_MAX)
        lines.append(f"  {slug}  v{version}  {display}")
        if summary:
            lines.append(f"    {summary}")
    return lines


def _format_show(slug: str, detail: dict[str, Any]) -> str:
    skill = detail.get("skill") or {}
    latest = detail.get("latestVersion") or {}
    owner = detail.get("owner") or {}
    meta = detail.get("metaContent") or {}
    display = skill.get("displayName", "")
    version = latest.get("version", "")
    owner_handle = owner.get("handle", "—") or "—"
    keywords = meta.get("Keywords")
    if isinstance(keywords, list) and keywords:
        kw_text = ", ".join(str(k) for k in keywords)
    else:
        kw_text = "—"
    license_text = meta.get("License") or "—"
    summary = skill.get("summary", "") or ""
    skill_md = meta.get("skillMd", "") or ""
    lines = [
        f"Skill: {slug}",
        f"  display     : {display}",
        f"  version     : v{version}",
        f"  owner       : {owner_handle}",
        f"  keywords    : {kw_text}",
        f"  license     : {license_text}",
        f"  summary     : {summary}",
        "",
        "--- SKILL.md ---",
        skill_md,
    ]
    return "\n".join(lines)


def _extract_zip_into(zip_bytes: bytes, target_dir) -> None:
    """Write zip bytes to a temp file, extract into `target_dir`."""
    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp.write(zip_bytes)
            tmp_path = tmp.name
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(tmp_path) as zf:
            zf.extractall(target_dir)
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ---------- registry HTTP ----------


def _http_get_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        body = resp.read()
    return json.loads(body.decode("utf-8"))


def _http_get_bytes(url: str) -> bytes:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
        return resp.read()


def _is_not_found(error: urllib.error.HTTPError) -> bool:
    if error.code == 404:
        return True
    try:
        body = error.read().decode("utf-8")
        payload = json.loads(body)
    except (ValueError, OSError):
        return False
    return payload.get("Code") == "SkillsHubNotFound"


def _registry_search(query: str, limit: int = 20) -> list[dict[str, Any]]:
    qs = urllib.parse.urlencode({"q": query, "limit": limit})
    url = f"{_REGISTRY_BASE}/search?{qs}"
    payload = _http_get_json(url)
    results = payload.get("results")
    if not isinstance(results, list):
        return []
    return results


def _registry_get_detail(slug: str) -> dict[str, Any] | None:
    url = f"{_REGISTRY_BASE}/skills/{urllib.parse.quote(slug)}"
    try:
        return _http_get_json(url)
    except urllib.error.HTTPError as e:
        if _is_not_found(e):
            return None
        raise


def _registry_download(slug: str, version: str) -> bytes:
    qs = urllib.parse.urlencode({"slug": slug, "version": version})
    url = f"{_REGISTRY_BASE}/download?{qs}"
    return _http_get_bytes(url)
