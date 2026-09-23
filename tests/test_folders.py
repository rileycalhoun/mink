"""Tests for the FolderStore (first-class session folders)."""

import pytest

from mink.config import settings
from mink.pipeline.folders import FolderStore


def _store(tmp_path, monkeypatch) -> FolderStore:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    return FolderStore()


def test_create_and_list_sorted(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    store.create("Zoology")
    store.create("Anthropology")
    assert [f.name for f in store.list()] == ["Anthropology", "Zoology"]


def test_create_rejects_blank_and_dedupes(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    with pytest.raises(ValueError):
        store.create("   ")
    a = store.create("Anthropology")
    b = store.create("anthropology")  # case-insensitive dedupe
    assert a.id == b.id
    assert len(store.list()) == 1


def test_rename(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    folder = store.create("Anthro")
    renamed = store.rename(folder.id, "Anthropology C1001")
    assert renamed is not None
    assert renamed.name == "Anthropology C1001"
    assert store.get(folder.id).name == "Anthropology C1001"
    assert store.rename("missing", "x") is None
    with pytest.raises(ValueError):
        store.rename(folder.id, "  ")


def test_delete(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    folder = store.create("Anthropology")
    assert store.delete(folder.id) is True
    assert store.get(folder.id) is None
    assert store.delete(folder.id) is False
