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
from rag.index.store import EmbeddedNote, Store, index_lock, open_index

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


def test_first_sync_indexes_every_note_and_records_the_commit(vault, publish):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    head = publish()
    stats = indexer.sync()
    assert (stats.indexed, stats.removed) == (2, 0)
    assert sources() == {"notes/aws-keys.md", "notes/cake.md"}
    assert Store().count() == stats.chunks > 0
    assert Store().indexed_commit() == head


def test_sync_applies_the_net_change_of_several_commits(vault, publish, vault_git, embedded):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    publish()
    indexer.sync()
    embedded.clear()
    (vault / "vpn.md").write_text(numbered(1))
    publish("add")
    (vault / "cake.md").write_text(CAKE.replace("forty", "fifty"))
    publish("modify")
    vault_git("rm", "-q", "notes/aws-keys.md")
    publish("delete")
    stats = indexer.sync()
    assert (stats.indexed, stats.removed) == (2, 1)
    assert sources() == {"notes/cake.md", "notes/vpn.md"}
    assert not any("AWS Keys" in text for text in embedded)  # the untouched note was not embedded


def test_a_second_sync_reads_nothing(vault, publish, monkeypatch):
    (vault / "aws-keys.md").write_text(AWS)
    publish()
    indexer.sync()
    monkeypatch.setattr(git, "read_files", lambda _c, paths: pytest.fail("read") if paths else [])
    monkeypatch.setattr(Store, "sources", lambda _self: pytest.fail("scan"))
    assert indexer.sync() == indexer.SyncStats()


def test_a_rename_removes_the_old_path_and_adds_the_new_one(vault, publish, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    publish()
    indexer.sync()
    vault_git("mv", "notes/aws-keys.md", "notes/aws-credentials.md")
    publish()
    stats = indexer.sync()
    assert (stats.indexed, stats.removed) == (1, 1)
    assert sources() == {"notes/aws-credentials.md"}


@pytest.mark.parametrize(
    "name", ["it's a note.md", "café notes.md", "-dash.md", 'say "hi".md', "line\nbreak.md"]
)
def test_unusual_file_names_are_indexed_and_removed(vault, publish, vault_git, name):
    (vault / name).write_text(AWS)
    publish()
    assert indexer.sync().indexed == 1 and sources() == {f"notes/{name}"}
    vault_git("rm", "-q", "--", f"notes/{name}")
    publish()
    assert indexer.sync().removed == 1 and sources() == set()


def test_only_committed_notes_are_indexed(vault, publish):
    (vault / "aws-keys.md").write_text(AWS)
    publish()
    indexer.sync()
    (vault / "aws-keys.md").write_text(AWS.replace("ninety", "sixty"))  # edited, not committed
    (vault / "cake.md").write_text(CAKE)  # new, not committed
    assert indexer.sync() == indexer.SyncStats()
    assert "ninety" in search.query("how often to rotate keys", Store())[0]["text"]


def test_unpushed_commits_and_deleted_drafts_are_never_embedded(
    vault, publish, vault_git, monkeypatch
):
    (vault / "aws-keys.md").write_text(AWS)
    published = publish()
    indexer.sync()
    monkeypatch.setattr(
        embeddings, "embed_documents", lambda _: pytest.fail("unpublished notes were embedded")
    )
    (vault / "draft.md").write_text(CAKE)
    vault_git("add", "-A")
    vault_git("commit", "-qm", "unpublished draft")
    assert indexer.sync() == indexer.SyncStats()
    with open_index() as index:
        assert index.indexed_commit() == published
        assert index.sources() == {"notes/aws-keys.md"}
    vault_git("rm", "-q", "notes/draft.md")
    vault_git("commit", "-qm", "remove before publishing")
    vault_git("update-ref", "refs/remotes/origin/main", "main")
    assert indexer.sync() == indexer.SyncStats()
    assert Store().indexed_commit() == vault_git("rev-parse", "main")


def test_local_branch_without_publication_is_not_a_search_source(vault, vault_git):
    (vault / "draft.md").write_text(CAKE)
    vault_git("add", "-A")
    vault_git("commit", "-qm", "local only")
    with pytest.raises(git.GitError, match="not indexed until pushed"):
        indexer.sync()


def test_the_index_follows_the_branch_whatever_is_checked_out(vault, publish, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    publish()
    indexer.sync()
    vault_git("checkout", "-q", "-b", "feature/new-note")
    (vault / "cake.md").write_text(CAKE)
    publish("a new note, not merged yet")
    assert indexer.sync() == indexer.SyncStats()
    assert sources() == {"notes/aws-keys.md"}
    vault_git("checkout", "-q", "main")
    vault_git("merge", "-q", "--no-ff", "-m", "merge", "feature/new-note")
    vault_git("update-ref", "refs/remotes/origin/main", "main")
    vault_git("checkout", "-q", "feature/new-note")
    assert indexer.sync().indexed == 1 and sources() == {"notes/aws-keys.md", "notes/cake.md"}


def test_a_rewritten_history_is_followed(vault, publish, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    publish()
    (vault / "cake.md").write_text(CAKE)
    publish()
    indexer.sync()
    vault_git("reset", "-q", "--hard", "HEAD~1")  # no git hook fires for this
    vault_git("update-ref", "refs/remotes/origin/main", "main")
    stats = indexer.sync()
    assert (stats.indexed, stats.removed) == (0, 1)  # the commit it was built from is gone
    assert sources() == {"notes/aws-keys.md"}


def test_a_branch_that_does_not_exist_says_how_to_fix_it(vault, publish, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    publish()
    vault_git("update-ref", "-d", "refs/remotes/origin/main")
    with pytest.raises(git.GitError, match=r"brain\.toml"):
        indexer.sync()


def test_the_indexed_branch_can_be_set(vault, publish, vault_git, monkeypatch):
    (vault / "aws-keys.md").write_text(AWS)
    publish()
    vault_git("branch", "trunk")
    vault_git("update-ref", "refs/remotes/origin/trunk", "trunk")
    monkeypatch.setattr(config, "BRANCH", "trunk")
    assert indexer.sync().indexed == 1


def test_notes_that_cannot_be_indexed_are_reported_and_leave_nothing_behind(vault, publish):
    (vault / "good.md").write_text(AWS)
    (vault / "stays-then-empties.md").write_text(CAKE)
    publish()
    indexer.sync()
    (vault / "empty.md").write_text("")
    (vault / "title-only.md").write_text("# Just a title\n")
    (vault / "setext-title.md").write_text("Just a title\n============\n")
    (vault / "bad.md").write_bytes(b"# Bad\n\nbroken \xff\xfe bytes " * 5)
    (vault / "stays-then-empties.md").write_text("")
    publish()
    stats = indexer.sync()
    assert set(stats.failed) == {
        "notes/empty.md",
        "notes/title-only.md",
        "notes/setext-title.md",
        "notes/bad.md",
        "notes/stays-then-empties.md",
    }
    assert sources() == {"notes/good.md"}


def test_oversized_notes_are_rejected_before_reading_and_leave_nothing_stale(
    vault, publish, monkeypatch, caplog
):
    limit = len(AWS.encode())
    monkeypatch.setattr(config, "MAX_NOTE_BYTES", limit)
    (vault / "big.md").write_text(AWS)
    publish()
    indexer.sync()
    (vault / "big.md").write_bytes(b"x" * (limit + 1))
    (vault / "good.md").write_text(AWS)
    publish()
    real_read = git.read_files

    def read_only_small_files(head, paths):
        assert paths == ["notes/good.md"]
        return real_read(head, paths)

    monkeypatch.setattr(git, "read_files", read_only_small_files)
    stats = indexer.sync()
    assert stats.indexed == 1
    assert stats.failed == {"notes/big.md": f"larger than {limit} bytes"}
    assert sources() == {"notes/good.md"}
    assert "skipped notes/big.md" in caplog.text


def test_a_utf8_bom_is_ignored(vault, publish):
    (vault / "aws-keys.md").write_bytes(b"\xef\xbb\xbf" + AWS.encode())
    publish()
    indexer.sync()
    assert search.query("rotate keys", Store())[0]["header_path"] == "AWS Keys > Rotation"


def test_a_sync_interrupted_while_embedding_is_repeated_without_duplicates(
    vault, publish, monkeypatch
):
    monkeypatch.setattr(config, "WRITE_BATCH_CHUNKS", 1)
    for i in range(3):
        (vault / f"note-{i}.md").write_text(numbered(i))
    publish()
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
    vault, publish, vault_git, monkeypatch
):
    (vault / "a.md").write_text(AWS)
    (vault / "b.md").write_text(CAKE)
    previous = publish()
    indexer.sync()
    (vault / "a.md").write_text(AWS.replace("ninety", "sixty"))
    (vault / "b.md").write_text(CAKE.replace("forty", "fifty"))
    publish()
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
    vault_git("update-ref", "refs/remotes/origin/main", previous)
    monkeypatch.setattr(embeddings, "embed_documents", real)
    with pytest.raises(RuntimeError, match="uv run rag sync"), open_index():
        pass
    indexer.sync()
    with open_index() as index:
        assert index.indexed_commit() == previous
        assert "ninety" in search.query("rotate keys", index)[0]["text"]
        assert "forty" in search.query("bake cake", index)[0]["text"]


def test_synced_index_with_rejected_notes_can_be_read(vault, publish, caplog):
    (vault / "good.md").write_text(AWS)
    (vault / "bad.md").write_bytes(b"not UTF-8: \xff")
    head = publish()
    indexer.sync()
    with open_index() as index:
        assert index.sources() == {"notes/good.md"} and index.indexed_commit() == head
    assert "skipped notes/bad.md" in caplog.text


def test_changed_settings_rebuild_the_index(vault, publish, monkeypatch, embedded):
    (vault / "aws-keys.md").write_text(AWS)
    publish()
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


def test_a_replacement_that_fails_keeps_the_old_note(vault, publish):
    (vault / "aws-keys.md").write_text(AWS)
    publish()
    indexer.sync()
    chunk = Chunk("new text", "AWS Keys", 0)
    broken = EmbeddedNote("notes/aws-keys.md", [chunk, chunk], [[0.0] * config.EMBEDDING_SIZE])
    with pytest.raises(ValueError):  # two chunks, one vector
        Store().replace_notes([broken])
    assert "Rotate AWS" in search.query("rotate keys", Store())[0]["text"]


def test_index_lock_is_held_through_retrieval(vault, publish):
    (vault / "cake.md").write_text(CAKE)
    publish()
    indexer.sync()
    (vault / "cake.md").write_text(CAKE.replace("forty", "fifty"))
    head = publish()
    indexer.sync()

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

    with open_index() as index:
        assert index.indexed_commit() == head and not lock_available()
        assert "fifty" in search.query("how long do I bake the cake", index)[0]["text"]
    assert lock_available()


def test_open_index_reads_cached_notes_regardless_of_checked_out_branch(vault, publish, vault_git):
    (vault / "cake.md").write_text(CAKE)
    main = publish()
    indexer.sync()
    vault_git("checkout", "-q", "-b", "feature/edit")
    (vault / "cake.md").write_text(CAKE.replace("forty", "fifty"))
    publish()
    with open_index() as index:
        assert index.indexed_commit() == main
        assert "forty" in search.query("how long do I bake the cake", index)[0]["text"]


def test_open_index_does_not_check_git_read_notes_or_write_the_index(vault, publish, monkeypatch):
    (vault / "aws-keys.md").write_text(AWS)
    publish()
    indexer.sync()
    with open_index() as index:
        version = index._table.version
        marker_inode = (config.DB_DIR / "indexed").stat().st_ino
    monkeypatch.setattr(git, "read_files", lambda *_: pytest.fail("read notes"))
    monkeypatch.setattr(Store, "sources", lambda _: pytest.fail("scan sources"))
    monkeypatch.setattr(Store, "rebuild_if_needed", lambda _: pytest.fail("rebuild"))
    monkeypatch.setattr(git, "remote_branch_tip", lambda *_: pytest.fail("check Git"))
    monkeypatch.setattr(indexer, "sync", lambda: pytest.fail("sync"))
    with open_index() as index:
        assert index._table.version == version
        assert (config.DB_DIR / "indexed").stat().st_ino == marker_inode


def test_status_reads_the_database_under_the_lock(vault, publish, monkeypatch):
    publish()
    Store()

    def open_store(*, create):
        assert not create
        with pytest.raises(Timeout), FileLock(config.LOCK_PATH).acquire(timeout=0):
            pass
        return Store(create=create)

    monkeypatch.setattr(indexer, "Store", open_store)
    indexer.status()


def test_status_does_not_recreate_a_missing_table(vault, publish):
    publish()
    index = Store()
    marker = (config.DB_DIR / "indexed").read_bytes()
    index._db.drop_table(store.TABLE)
    with pytest.raises(RuntimeError, match="uv run rag sync"):
        indexer.status()
    assert store.TABLE not in index._db.list_tables().tables
    assert (config.DB_DIR / "indexed").read_bytes() == marker


def test_status_does_not_rebuild_an_incompatible_index(vault, publish, monkeypatch):
    (vault / "aws-keys.md").write_text(AWS)
    publish()
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


def test_status_compares_the_index_with_git(vault, publish, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    head = publish()
    before = indexer.status()
    assert (before.pending, before.indexed_commit, before.branch_tip) == (1, None, head)
    assert (before.notes, before.chunks) == (0, 0)
    assert not config.DB_DIR.exists()
    indexer.sync()
    assert indexer.status().pending == 0 and indexer.status().notes == 1
    (vault / "aws-keys.md").write_text(AWS + "\nMore.\n")
    (vault / "cake.md").write_text(CAKE)
    publish()
    assert indexer.status().pending == 2


def test_a_sync_waits_for_another_one_to_finish(vault, publish):
    (vault / "aws-keys.md").write_text(AWS)
    publish()
    holding = threading.Event()

    def other_process():
        with index_lock():
            holding.set()
            time.sleep(0.5)

    threading.Thread(target=other_process).start()
    holding.wait()
    started = time.monotonic()
    assert indexer.sync().indexed == 1
    assert time.monotonic() - started >= 0.4


def test_a_search_does_not_wait_forever_for_a_sync(vault, publish, monkeypatch):
    (vault / "cake.md").write_text(CAKE)
    publish()
    indexer.sync()
    monkeypatch.setattr(config, "READ_LOCK_TIMEOUT", 0.1)
    with index_lock():
        with pytest.raises(RuntimeError, match="synchronized"), open_index():
            pass
        with pytest.raises(RuntimeError, match="synchronized"):
            indexer.status()


def fragments() -> int:
    return Store()._table.stats()["fragment_stats"]["num_fragments"]


def test_notes_are_written_in_batches_and_small_syncs_are_compacted(vault, publish, monkeypatch):
    monkeypatch.setattr(config, "WRITE_BATCH_CHUNKS", 40)
    for i in range(60):
        (vault / f"note-{i}.md").write_text(numbered(i))
    publish()
    indexer.sync()
    assert fragments() <= 10  # not one per note
    for i in range(60, 72):  # twelve pulls, one new note each
        (vault / f"note-{i}.md").write_text(numbered(i))
        publish()
        indexer.sync()
    assert fragments() <= 12


def test_deleted_rows_are_compacted_away(vault, publish, vault_git):
    for i in range(10):
        (vault / f"note-{i}.md").write_text(numbered(i))
    publish()
    indexer.sync()
    for i in range(6):
        vault_git("rm", "-q", f"notes/note-{i}.md")
    publish()
    indexer.sync()
    assert Store()._table.stats()["num_deleted_rows"] == 0
