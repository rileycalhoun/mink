"""Folders: first-class organization for lecture sessions.

A folder is just an id + name; sessions reference it via ``folder_id``.
Folders live in ``data/folders.json`` so empty folders survive and renames
propagate without touching every session file.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from mink.config import settings


@dataclass
class Folder:
    id: str = field(default_factory=lambda: uuid4().hex[:8])
    name: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> Folder:
        data = dict(data)
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


class FolderStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or settings.data_dir / "folders.json"

    def _read(self) -> list[Folder]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            return []
        folders: list[Folder] = []
        for item in data:
            try:
                folders.append(Folder.from_dict(item))
            except (KeyError, ValueError, TypeError):
                continue
        return folders

    def _write(self, folders: list[Folder]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([f.to_dict() for f in folders], indent=2))

    def list(self) -> list[Folder]:
        folders = self._read()
        folders.sort(key=lambda f: f.name.lower())
        return folders

    def get(self, folder_id: str) -> Folder | None:
        for folder in self._read():
            if folder.id == folder_id:
                return folder
        return None

    def find_by_name(self, name: str) -> Folder | None:
        wanted = name.strip().lower()
        for folder in self._read():
            if folder.name.strip().lower() == wanted:
                return folder
        return None

    def create(self, name: str) -> Folder:
        """Create a folder; returns the existing one if the name is taken."""
        name = name.strip()
        if not name:
            raise ValueError("Folder name cannot be empty")
        existing = self.find_by_name(name)
        if existing is not None:
            return existing
        folders = self._read()
        folder = Folder(name=name)
        folders.append(folder)
        self._write(folders)
        return folder

    def rename(self, folder_id: str, name: str) -> Folder | None:
        name = name.strip()
        if not name:
            raise ValueError("Folder name cannot be empty")
        folders = self._read()
        for folder in folders:
            if folder.id == folder_id:
                folder.name = name
                self._write(folders)
                return folder
        return None

    def delete(self, folder_id: str) -> bool:
        folders = self._read()
        kept = [f for f in folders if f.id != folder_id]
        if len(kept) == len(folders):
            return False
        self._write(kept)
        return True
