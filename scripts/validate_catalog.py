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
ID_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
SHA_RE = re.compile(r"[a-f0-9]{40}\Z")
HASH_RE = re.compile(r"[a-f0-9]{64}\Z")
VERSION_RE = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?\Z")


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
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    require(isinstance(catalog, dict), "catalog must be an object")
    require(set(catalog) == {"schemaVersion", "publisher", "skills"}, "unexpected top-level fields")
    require(type(catalog["schemaVersion"]) is int and catalog["schemaVersion"] == 1, "schemaVersion must be 1")
    require(catalog["publisher"] == "ATMT Labs", "publisher must be ATMT Labs")
    require(isinstance(catalog["skills"], list) and catalog["skills"], "skills must be a non-empty array")

    seen_ids: set[str] = set()
    for skill in catalog["skills"]:
        require(isinstance(skill, dict), "skill must be an object")
        require(
            set(skill) == {"id", "name", "description", "category", "version", "sourceCommit", "files"},
            "unexpected skill fields",
        )
        skill_id = skill["id"]
        require(isinstance(skill_id, str) and bool(ID_RE.fullmatch(skill_id)), "invalid skill id")
        require(skill_id not in seen_ids, f"duplicate skill id: {skill_id}")
        seen_ids.add(skill_id)
        for field in ("name", "description", "category"):
            require(isinstance(skill[field], str) and bool(skill[field].strip()), f"{skill_id}: invalid {field}")
        require(len(skill["name"]) <= 120 and len(skill["description"]) <= 500 and len(skill["category"]) <= 80, f"{skill_id}: metadata too long")
        require(isinstance(skill["version"], str) and bool(VERSION_RE.fullmatch(skill["version"])), f"{skill_id}: invalid version")
        commit = skill["sourceCommit"]
        require(isinstance(commit, str) and bool(SHA_RE.fullmatch(commit)), f"{skill_id}: sourceCommit must be a full lowercase commit SHA")
        result = subprocess.run(["git", "cat-file", "-t", commit], cwd=ROOT, capture_output=True, text=True, check=False)
        require(result.returncode == 0 and result.stdout.strip() == "commit", f"{skill_id}: sourceCommit is not a local commit")
        files = skill["files"]
        require(isinstance(files, list) and files, f"{skill_id}: files must be non-empty")
        declared: set[str] = set()
        for entry in files:
            require(isinstance(entry, dict) and set(entry) == {"path", "sha256", "size"}, f"{skill_id}: invalid file entry")
            path = entry["path"]
            require(isinstance(path, str) and "\\" not in path and "\x00" not in path, f"{skill_id}: invalid path")
            posix = PurePosixPath(path)
            require(not posix.is_absolute() and posix.as_posix() == path and ".." not in posix.parts, f"{skill_id}: unsafe path")
            require(len(posix.parts) >= 3 and posix.parts[:2] == ("skills", skill_id), f"{skill_id}: path must be inside skill directory")
            require(path not in declared, f"{skill_id}: duplicate file: {path}")
            declared.add(path)
            file = ROOT.joinpath(*posix.parts)
            require(file.is_file() and not file.is_symlink(), f"{path}: file missing or symlinked")
            data = file.read_bytes()
            require(isinstance(entry["size"], int) and not isinstance(entry["size"], bool) and entry["size"] == len(data), f"{path}: size mismatch")
            require(len(data) <= 1_000_000, f"{path}: file exceeds 1 MB")
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
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f"Catalog invalid: {error}", file=sys.stderr)
        raise SystemExit(1)
    print("Catalog valid")
