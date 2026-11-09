import hashlib
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from filelock import FileLock, Timeout
from samples import AWS, CAKE, numbered

from rag import config, git
from rag.index import chunker, embeddings, indexer, search, store
from rag.index.chunker import Chunk
from rag.index.store import EmbeddedNote, Store, write_lock

PER_NOTE = len(chunker.chunk_markdown(AWS, "notes/x.md"))


@pytest.fixture
def embedded(monkeypatch):
    """Every text sent to the embedder."""
    texts: list[str] = []
    real = embeddings.embed_documents
    monkeypatch.setattr(embeddings, "embed_documents", lambda t: texts.extend(t) or real(t))
    return texts


def sources() -> set[str]:
    return Store().sources()


def test_first_sync_indexes_every_note_and_records_the_commit(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    head = commit()
    stats = indexer.sync()
    assert (stats.indexed, stats.removed) == (2, 0)
    assert sources() == {"notes/aws-keys.md", "notes/cake.md"}
    assert Store().count() == stats.chunks > 0
    assert Store().indexed_commit() == head


def test_sync_applies_the_net_change_of_several_commits(vault, commit, vault_git, embedded):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    commit()
    indexer.sync()
    embedded.clear()
    (vault / "vpn.md").write_text(numbered(1))
    commit("add")
    (vault / "cake.md").write_text(CAKE.replace("forty", "fifty"))
    commit("modify")
    vault_git("rm", "-q", "notes/aws-keys.md")
    commit("delete")
    stats = indexer.sync()
    assert (stats.indexed, stats.removed) == (2, 1)
    assert sources() == {"notes/cake.md", "notes/vpn.md"}
    assert not any("AWS Keys" in text for text in embedded)  # the untouched note was not embedded


def test_a_second_sync_reads_nothing(vault, commit, monkeypatch):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    indexer.sync()
    monkeypatch.setattr(git, "read_files", lambda _c, paths: pytest.fail("read") if paths else [])
    monkeypatch.setattr(Store, "sources", lambda _self: pytest.fail("scan"))
    assert indexer.sync() == indexer.SyncStats()


def test_a_rename_removes_the_old_path_and_adds_the_new_one(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    indexer.sync()
    vault_git("mv", "notes/aws-keys.md", "notes/aws-credentials.md")
    commit()
    stats = indexer.sync()
    assert (stats.indexed, stats.removed) == (1, 1)
    assert sources() == {"notes/aws-credentials.md"}


@pytest.mark.parametrize(
    "name", ["it's a note.md", "café notes.md", "-dash.md", 'say "hi".md', "line\nbreak.md"]
)
def test_unusual_file_names_are_indexed_and_removed(vault, commit, vault_git, name):
    (vault / name).write_text(AWS)
    commit()
    assert indexer.sync().indexed == 1 and sources() == {f"notes/{name}"}
    vault_git("rm", "-q", "--", f"notes/{name}")
    commit()
    assert indexer.sync().removed == 1 and sources() == set()


def test_only_committed_notes_are_indexed(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    indexer.sync()
    (vault / "aws-keys.md").write_text(AWS.replace("ninety", "sixty"))  # edited, not committed
    (vault / "cake.md").write_text(CAKE)  # new, not committed
    assert indexer.sync() == indexer.SyncStats()
    assert "ninety" in search.query("how often to rotate keys", Store())[0]["text"]


def test_the_index_follows_the_branch_whatever_is_checked_out(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    indexer.sync()
    vault_git("checkout", "-q", "-b", "feature/new-note")
    (vault / "cake.md").write_text(CAKE)
    commit("a new note, not merged yet")
    assert indexer.sync() == indexer.SyncStats()
    assert sources() == {"notes/aws-keys.md"}
    vault_git("checkout", "-q", "main")
    vault_git("merge", "-q", "--no-ff", "-m", "merge", "feature/new-note")
    vault_git("checkout", "-q", "feature/new-note")
    assert indexer.sync().indexed == 1 and sources() == {"notes/aws-keys.md", "notes/cake.md"}


def test_a_rewritten_history_is_followed(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    (vault / "cake.md").write_text(CAKE)
    commit()
    indexer.sync()
    vault_git("reset", "-q", "--hard", "HEAD~1")  # no git hook fires for this
    stats = indexer.sync()
    assert (stats.indexed, stats.removed) == (0, 1)  # the commit it was built from is gone
    assert sources() == {"notes/aws-keys.md"}


def test_a_branch_that_does_not_exist_says_how_to_fix_it(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    vault_git("branch", "-m", "main", "trunk")
    with pytest.raises(git.GitError, match=r"brain\.toml"):
        indexer.sync()


def test_the_indexed_branch_can_be_set(vault, commit, vault_git, monkeypatch):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    vault_git("branch", "trunk")
    monkeypatch.setattr(config, "BRANCH", "trunk")
    assert indexer.sync().indexed == 1


def test_notes_that_cannot_be_indexed_are_reported_and_leave_nothing_behind(vault, commit):
    (vault / "good.md").write_text(AWS)
    (vault / "stays-then-empties.md").write_text(CAKE)
    commit()
    indexer.sync()
    (vault / "empty.md").write_text("")
    (vault / "title-only.md").write_text("# Just a title\n")
    (vault / "setext-title.md").write_text("Just a title\n============\n")
    (vault / "bad.md").write_bytes(b"# Bad\n\nbroken \xff\xfe bytes " * 5)
    (vault / "stays-then-empties.md").write_text("")
    commit()
    stats = indexer.sync()
    assert set(stats.failed) == {
        "notes/empty.md",
        "notes/title-only.md",
        "notes/setext-title.md",
        "notes/bad.md",
        "notes/stays-then-empties.md",
    }
    assert sources() == {"notes/good.md"}


def test_a_note_larger_than_the_limit_is_reported(vault, commit, monkeypatch):
    monkeypatch.setattr(config, "MAX_NOTE_BYTES", 100)
    (vault / "big.md").write_text(AWS)
    commit()
    assert "larger than" in indexer.sync().failed["notes/big.md"]


def test_a_utf8_bom_is_ignored(vault, commit):
    (vault / "aws-keys.md").write_bytes(b"\xef\xbb\xbf" + AWS.encode())
    commit()
    indexer.sync()
    assert search.query("rotate keys", Store())[0]["header_path"] == "AWS Keys > Rotation"


def test_a_sync_interrupted_while_embedding_is_repeated_without_duplicates(
    vault, commit, monkeypatch
):
    monkeypatch.setattr(config, "WRITE_BATCH_CHUNKS", 1)
    for i in range(3):
        (vault / f"note-{i}.md").write_text(numbered(i))
    commit()
    real, calls = embeddings.embed_documents, []

    def fails_the_second_time(texts):
        calls.append(1)
        if len(calls) == 2:
            raise OSError("disk full")
        return real(texts)

    monkeypatch.setattr(embeddings, "embed_documents", fails_the_second_time)
    with pytest.raises(OSError):
        indexer.sync()
    assert Store().indexed_commit() is None  # the commit is recorded last
    monkeypatch.setattr(embeddings, "embed_documents", real)
    indexer.sync()
    assert len(sources()) == 3 and Store().count() == 3 * PER_NOTE


def test_a_partial_sync_cannot_look_current_after_the_branch_moves_back(
    vault, commit, vault_git, monkeypatch
):
    (vault / "a.md").write_text(AWS)
    (vault / "b.md").write_text(CAKE)
    previous = commit()
    indexer.sync()
    (vault / "a.md").write_text(AWS.replace("ninety", "sixty"))
    (vault / "b.md").write_text(CAKE.replace("forty", "fifty"))
    commit()
    monkeypatch.setattr(config, "WRITE_BATCH_CHUNKS", 1)
    real, calls = embeddings.embed_documents, []

    def interrupted(texts):
        calls.append(1)
        if len(calls) == 2:
            raise OSError("disk full")
        return real(texts)

    monkeypatch.setattr(embeddings, "embed_documents", interrupted)
    with pytest.raises(OSError, match="disk full"):
        indexer.sync()
    assert Store().indexed_commit() is None
    assert "sixty" in search.query("rotate keys", Store())[0]["text"]
    vault_git("update-ref", "refs/heads/main", previous)
    monkeypatch.setattr(embeddings, "embed_documents", real)
    with indexer.prepare_index() as index:
        assert index.indexed_commit() == previous
        assert "ninety" in search.query("rotate keys", index)[0]["text"]
        assert "forty" in search.query("bake cake", index)[0]["text"]


def test_automatic_preparation_reports_rejected_notes(vault, commit, caplog):
    (vault / "good.md").write_text(AWS)
    (vault / "bad.md").write_bytes(b"not UTF-8: \xff")
    head = commit()
    with indexer.prepare_index() as index:
        assert index.sources() == {"notes/good.md"} and index.indexed_commit() == head
    assert "skipped notes/bad.md" in caplog.text


def test_changed_settings_rebuild_the_index(vault, commit, monkeypatch, embedded):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    indexer.sync()
    embedded.clear()
    monkeypatch.setattr(store, "FINGERPRINT", "other settings")
    assert indexer.sync().indexed == 1 and embedded
    assert (config.DB_DIR / "indexed").read_text().startswith("other settings")


def test_the_fingerprint_covers_the_settings_and_the_chunker_code():
    settings = (
        config.MODEL,
        config.EMBEDDING_SIZE,
        config.MODEL_MAX_TOKENS,
        config.MAX_CHUNK_SIZE,
        config.MIN_CHUNK_SIZE,
        tuple(config.SKIP_HEADINGS),
        tuple(config.SKIP_FOLDERS),
        Path(chunker.__file__).read_bytes(),
    )
    assert hashlib.sha256(repr(settings).encode()).hexdigest() == store.FINGERPRINT


def test_a_replacement_that_fails_keeps_the_old_note(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    indexer.sync()
    chunk = Chunk("new text", "AWS Keys", 0)
    broken = EmbeddedNote("notes/aws-keys.md", [chunk, chunk], [[0.0] * config.EMBEDDING_SIZE])
    with pytest.raises(ValueError):  # two chunks, one vector
        Store().replace_notes([broken])
    assert "Rotate AWS" in search.query("rotate keys", Store())[0]["text"]


def test_preparation_refreshes_commits_and_holds_the_lock_through_retrieval(vault, commit):
    (vault / "cake.md").write_text(CAKE)
    commit()
    indexer.sync()
    (vault / "cake.md").write_text(CAKE.replace("forty", "fifty"))
    head = commit()

    def lock_available():
        code = (
            "import sys\n"
            "from filelock import FileLock, Timeout\n"
            "try:\n"
            "    with FileLock(sys.argv[1]).acquire(timeout=0.05): print('free')\n"
            "except Timeout: print('busy')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(config.LOCK_PATH)],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return result.stdout.strip() == "free"

    with indexer.prepare_index() as index:
        assert index.indexed_commit() == head and not lock_available()
        assert "fifty" in search.query("how long do I bake the cake", index)[0]["text"]
    assert lock_available()


def test_preparation_uses_the_configured_branch_not_the_checked_out_one(vault, commit, vault_git):
    (vault / "cake.md").write_text(CAKE)
    main = commit()
    vault_git("checkout", "-q", "-b", "feature/edit")
    (vault / "cake.md").write_text(CAKE.replace("forty", "fifty"))
    commit()
    with indexer.prepare_index() as index:
        assert index.indexed_commit() == main
        assert "forty" in search.query("how long do I bake the cake", index)[0]["text"]


def test_preparing_a_current_index_does_not_read_notes_or_write_it_again(
    vault, commit, monkeypatch
):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    with indexer.prepare_index() as index:
        version = index._table.version
        marker_inode = (config.DB_DIR / "indexed").stat().st_ino
    monkeypatch.setattr(git, "read_files", lambda *_: pytest.fail("read notes"))
    monkeypatch.setattr(Store, "sources", lambda _: pytest.fail("scan sources"))
    monkeypatch.setattr(Store, "rebuild_if_needed", lambda _: pytest.fail("rebuild"))
    with indexer.prepare_index() as index:
        assert index._table.version == version
        assert (config.DB_DIR / "indexed").stat().st_ino == marker_inode


def test_status_reads_the_database_under_the_lock(vault, commit, monkeypatch):
    commit()

    def open_store():
        with pytest.raises(Timeout), FileLock(config.LOCK_PATH).acquire(timeout=0):
            pass
        return Store()

    monkeypatch.setattr(indexer, "Store", open_store)
    indexer.status()


def test_status_does_not_rebuild_an_incompatible_index(vault, commit, monkeypatch):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    indexer.sync()
    marker = (config.DB_DIR / "indexed").read_bytes()
    chunks = Store().count()
    version = Store()._table.version
    monkeypatch.setattr(store, "FINGERPRINT", "changed settings")
    status = indexer.status()
    assert (status.notes, status.chunks, status.pending, status.indexed_commit) == (
        1,
        chunks,
        1,
        None,
    )
    assert Store()._table.version == version
    assert (config.DB_DIR / "indexed").read_bytes() == marker


def test_status_compares_the_index_with_git(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    head = commit()
    before = indexer.status()
    assert (before.pending, before.indexed_commit, before.branch_tip) == (1, None, head)
    indexer.sync()
    assert indexer.status().pending == 0 and indexer.status().notes == 1
    (vault / "aws-keys.md").write_text(AWS + "\nMore.\n")
    (vault / "cake.md").write_text(CAKE)
    commit()
    assert indexer.status().pending == 2


def test_a_sync_waits_for_another_one_to_finish(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    holding = threading.Event()

    def other_process():
        with write_lock():
            holding.set()
            time.sleep(0.5)

    threading.Thread(target=other_process).start()
    holding.wait()
    started = time.monotonic()
    assert indexer.sync().indexed == 1
    assert time.monotonic() - started >= 0.4


def fragments() -> int:
    return Store()._table.stats()["fragment_stats"]["num_fragments"]


def test_notes_are_written_in_batches_and_small_syncs_are_compacted(vault, commit, monkeypatch):
    monkeypatch.setattr(config, "WRITE_BATCH_CHUNKS", 40)
    for i in range(60):
        (vault / f"note-{i}.md").write_text(numbered(i))
    commit()
    indexer.sync()
    assert fragments() <= 10  # not one per note
    for i in range(60, 72):  # twelve pulls, one new note each
        (vault / f"note-{i}.md").write_text(numbered(i))
        commit()
        indexer.sync()
    assert fragments() <= 12


def test_deleted_rows_are_compacted_away(vault, commit, vault_git):
    for i in range(10):
        (vault / f"note-{i}.md").write_text(numbered(i))
    commit()
    indexer.sync()
    for i in range(6):
        vault_git("rm", "-q", f"notes/note-{i}.md")
    commit()
    indexer.sync()
    assert Store()._table.stats()["num_deleted_rows"] == 0


def test_a_vector_index_is_built_and_kept_current(vault, commit, monkeypatch):
    monkeypatch.setattr(config, "INDEX_AFTER_ROWS", 4)
    (vault / "aws-keys.md").write_text(AWS * 2)
    (vault / "cake.md").write_text(CAKE * 2)
    commit()
    indexer.sync()
    assert Store()._has_vector_index()
    (vault / "vpn.md").write_text(numbered(1) * 2)
    commit()
    indexer.sync()
    assert Store()._table.index_stats(store.VECTOR_INDEX).num_unindexed_rows == 0
