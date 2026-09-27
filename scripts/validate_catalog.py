#!/usr/bin/env python3
"""Check that the published catalog identifies exactly the reviewed skill files."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "catalog.json"
ID_RE = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
SHA_RE = re.compile(r"[a-f0-9]{40}\Z")
HASH_RE = re.compile(r"[a-f0-9]{64}\Z")
VERSION_RE = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)\Z")
SEGMENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")
WINDOWS_RESERVED_RE = re.compile(r"(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?\Z", re.IGNORECASE)
MAX_CATALOG_BYTES = 512 * 1024
MAX_SKILLS = 200
MAX_FILES = 60
MAX_FILE_BYTES = 512 * 1024
MAX_SKILL_BYTES = 2 * 1024 * 1024
MAX_FILE_DEPTH = 5


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def git_blob(commit: str, path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    require(result.returncode == 0, f"{path}: unavailable in sourceCommit {commit}")
    return result.stdout


def validate_frontmatter(path: Path, skill_id: str) -> None:
    content = path.read_text(encoding="utf-8")
    require(content.startswith("---\n"), f"{path}: missing YAML frontmatter")
    end = content.find("\n---\n", 4)
    require(end >= 0, f"{path}: unclosed YAML frontmatter")
    lines = content[4:end].splitlines()
    names = [line[5:].strip() for line in lines if line.startswith("name:")]
    descriptions = [line[12:].strip() for line in lines if line.startswith("description:")]
    require(names == [skill_id], f"{path}: frontmatter name must match catalog id")
    require(len(descriptions) == 1 and bool(descriptions[0]), f"{path}: missing description")
    require("[TODO:" not in content, f"{path}: unfinished placeholder")


def validate() -> None:
    raw_catalog = CATALOG.read_bytes()
    require(len(raw_catalog) <= MAX_CATALOG_BYTES, "catalog exceeds 512 KiB")
    catalog = json.loads(raw_catalog.decode("utf-8"))
    require(isinstance(catalog, dict), "catalog must be an object")
    require(set(catalog) == {"schemaVersion", "publisher", "skills"}, "unexpected top-level fields")
    require(type(catalog["schemaVersion"]) is int and catalog["schemaVersion"] == 1, "schemaVersion must be 1")
    require(catalog["publisher"] == "ATMT Labs", "publisher must be ATMT Labs")
    require(isinstance(catalog["skills"], list) and 0 < len(catalog["skills"]) <= MAX_SKILLS, "invalid number of skills")

    seen_ids: set[str] = set()
    for skill in catalog["skills"]:
        require(isinstance(skill, dict), "skill must be an object")
        require(
            set(skill) == {"id", "name", "description", "category", "version", "sourceCommit", "files"},
            "unexpected skill fields",
        )
        skill_id = skill["id"]
        require(isinstance(skill_id, str) and bool(ID_RE.fullmatch(skill_id)) and not WINDOWS_RESERVED_RE.fullmatch(skill_id), "invalid skill id")
        require(skill_id not in seen_ids, f"duplicate skill id: {skill_id}")
        seen_ids.add(skill_id)
        for field, limit in (("name", 100), ("description", 500), ("category", 80)):
            value = skill[field]
            require(isinstance(value, str) and bool(value.strip()) and len(value) <= limit and not CONTROL_RE.search(value), f"{skill_id}: invalid {field}")
        version = skill["version"]
        require(isinstance(version, str) and len(version) <= 32 and bool(VERSION_RE.fullmatch(version)) and all(int(part) <= 9_007_199_254_740_991 for part in version.split(".")), f"{skill_id}: invalid version")
        commit = skill["sourceCommit"]
        require(isinstance(commit, str) and bool(SHA_RE.fullmatch(commit)), f"{skill_id}: sourceCommit must be a full lowercase commit SHA")
        result = subprocess.run(["git", "cat-file", "-t", commit], cwd=ROOT, capture_output=True, text=True, check=False)
        require(result.returncode == 0 and result.stdout.strip() == "commit", f"{skill_id}: sourceCommit is not a local commit")
        files = skill["files"]
        require(isinstance(files, list) and 0 < len(files) <= MAX_FILES, f"{skill_id}: invalid number of files")
        declared: set[str] = set()
        declared_lower: set[str] = set()
        total_size = 0
        for entry in files:
            require(isinstance(entry, dict) and set(entry) == {"path", "sha256", "size"}, f"{skill_id}: invalid file entry")
            path = entry["path"]
            require(isinstance(path, str) and path.startswith(f"skills/{skill_id}/"), f"{skill_id}: invalid path")
            posix = PurePosixPath(path)
            require(not posix.is_absolute() and posix.as_posix() == path and ".." not in posix.parts, f"{skill_id}: unsafe path")
            require(len(posix.parts) >= 3 and posix.parts[:2] == ("skills", skill_id), f"{skill_id}: path must be inside skill directory")
            rel = path[len(f"skills/{skill_id}/"):]
            segments = rel.split("/")
            require(len(rel) <= 240 and len(segments) <= MAX_FILE_DEPTH and all(SEGMENT_RE.fullmatch(part) and ".." not in part and not part.endswith(".") and not WINDOWS_RESERVED_RE.fullmatch(part) for part in segments), f"{skill_id}: invalid path segments")
            require(rel.lower() != ".atmt-skill.json", f"{skill_id}: reserved filename")
            require(rel.lower() not in declared_lower, f"{skill_id}: duplicate file: {path}")
            declared.add(path)
            declared_lower.add(rel.lower())
            file = ROOT.joinpath(*posix.parts)
            require(file.is_file() and not file.is_symlink(), f"{path}: file missing or symlinked")
            data = file.read_bytes()
            require(isinstance(entry["size"], int) and not isinstance(entry["size"], bool) and entry["size"] == len(data), f"{path}: size mismatch")
            require(len(data) <= MAX_FILE_BYTES, f"{path}: file exceeds 512 KiB")
            total_size += len(data)
            require(total_size <= MAX_SKILL_BYTES, f"{skill_id}: files exceed 2 MiB")
            digest = hashlib.sha256(data).hexdigest()
            require(isinstance(entry["sha256"], str) and bool(HASH_RE.fullmatch(entry["sha256"])) and entry["sha256"] == digest, f"{path}: SHA-256 mismatch")
            require(git_blob(commit, path) == data, f"{path}: differs from pinned sourceCommit")
        require(f"skills/{skill_id}/SKILL.md" in declared, f"{skill_id}: SKILL.md not listed")
        directory = ROOT / "skills" / skill_id
        actual = {p.relative_to(ROOT).as_posix() for p in directory.rglob("*") if p.is_file()}
        require(actual == declared, f"{skill_id}: files in directory do not match catalog")
        validate_frontmatter(directory / "SKILL.md", skill_id)

    actual_ids = {p.name for p in (ROOT / "skills").iterdir() if p.is_dir()}
    require(actual_ids == seen_ids, "skill directories do not match catalog entries")


if __name__ == "__main__":
    try:
        validate()
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"Catalog invalid: {error}", file=sys.stderr)
        raise SystemExit(1)
    print("Catalog valid")
