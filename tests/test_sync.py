import hashlib
import threading
import time
from pathlib import Path

import pytest
from filelock import FileLock

import rag
from rag import chunker, cli, config, db, embeddings, git
from rag.chunker import Chunk
from rag.db import EmbeddedNote, Index

AWS = (
    "# AWS Keys\n\nTags: #aws #handbook\n\n## Rotation\n\n"
    "Rotate AWS access keys every ninety days and delete the old ones. Long-lived "
    "credentials are a security risk, so rotation is mandatory for every service account.\n"
)
CAKE = (
    "# Cake\n\nTags: #food #handbook\n\n## Recipe\n\n"
    "Mix flour, eggs and sugar, then bake the chocolate cake for forty minutes. Let it "
    "cool on a rack before adding the frosting, otherwise the frosting melts.\n"
)
PER_NOTE = len(chunker.chunk_markdown(AWS, "notes/x.md"))  # the title folds into the one section


@pytest.fixture
def embedded(monkeypatch):
    """Records every text sent to the embedder, to prove what was (re)embedded."""
    texts: list[str] = []
    real = embeddings.embed_documents
    monkeypatch.setattr(embeddings, "embed_documents", lambda t: texts.extend(t) or real(t))
    return texts


def sources() -> set[str]:
    return Index().sources()


def chunk_count() -> int:
    return Index().count()


def hit_sources(question: str, n: int = 10) -> set[str]:
    return {hit["source"] for hit in rag.query(question, n)}


# ---- the basics: what git reports is what gets indexed --------------------------------------


def test_first_sync_indexes_every_note_and_records_the_commit(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    head = commit()
    stats = rag.sync()
    assert (stats.indexed, stats.removed) == (2, 0)
    assert sources() == {"notes/aws-keys.md", "notes/cake.md"}
    assert chunk_count() == stats.chunks > 0
    assert Index().indexed_commit() == head


def test_second_sync_does_nothing_at_all(vault, commit, embedded, monkeypatch):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    embedded.clear()
    monkeypatch.setattr(
        git, "read_notes", lambda _commit, notes: pytest.fail("read") if notes else []
    )
    monkeypatch.setattr(chunker, "chunk_markdown", lambda *_: pytest.fail("a note was chunked"))
    assert rag.sync() == rag.SyncStats()
    assert embedded == []


def test_added_note_is_the_only_one_indexed(vault, commit, embedded):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    embedded.clear()
    (vault / "cake.md").write_text(CAKE)
    commit()
    stats = rag.sync()
    assert (stats.indexed, stats.removed) == (1, 0)
    assert embedded and all("Cake" in text for text in embedded)
    assert sources() == {"notes/aws-keys.md", "notes/cake.md"}


def test_modified_note_is_the_only_one_reindexed(vault, commit, embedded):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    commit()
    rag.sync()
    embedded.clear()
    (vault / "cake.md").write_text(CAKE.replace("forty", "fifty"))
    commit()
    assert rag.sync().indexed == 1
    assert embedded and all("Cake" in text for text in embedded)
    hits = rag.query("how long do I bake the cake", 1)
    assert "fifty" in hits[0]["text"] and "forty" not in hits[0]["text"]


def test_deleted_note_is_removed(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    commit()
    rag.sync()
    vault_git("rm", "-q", "notes/cake.md")
    commit()
    stats = rag.sync()
    assert (stats.indexed, stats.removed) == (0, 1)
    assert sources() == {"notes/aws-keys.md"}


def test_a_pull_with_several_commits_applies_the_net_change(vault, commit, vault_git, embedded):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    commit()
    rag.sync()
    embedded.clear()
    (vault / "vpn.md").write_text(AWS.replace("AWS Keys", "VPN").replace("keys", "tokens"))
    commit("add")
    (vault / "cake.md").write_text(CAKE.replace("forty", "fifty"))
    commit("modify")
    vault_git("rm", "-q", "notes/aws-keys.md")
    commit("delete")
    (vault / "vpn.md").write_text((vault / "vpn.md").read_text() + "\nMore about tokens.\n")
    commit("modify the new one")
    stats = rag.sync()
    assert (stats.indexed, stats.removed) == (2, 1)
    assert sources() == {"notes/cake.md", "notes/vpn.md"}
    assert not any("AWS Keys" in text for text in embedded)


def test_renamed_note_moves(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    vault_git("mv", "notes/aws-keys.md", "notes/aws-credentials.md")
    commit()
    stats = rag.sync()
    assert (stats.indexed, stats.removed) == (1, 1)
    assert sources() == {"notes/aws-credentials.md"}


def test_uncommitted_edits_wait_for_their_commit(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    (vault / "aws-keys.md").write_text(AWS.replace("ninety", "sixty"))  # edited, not committed
    (vault / "cake.md").write_text(CAKE)  # new, not committed
    assert rag.sync() == rag.SyncStats()
    assert sources() == {"notes/aws-keys.md"}
    commit()
    assert rag.sync().indexed == 2
    assert "sixty" in rag.query("how often to rotate keys", 1)[0]["text"]


def test_only_markdown_under_notes_and_outside_hidden_folders_is_indexed(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    (vault / ".trash").mkdir()
    (vault / ".trash" / "deleted.md").write_text(CAKE)
    (vault / "sub" / ".hidden").mkdir(parents=True)
    (vault / "sub" / ".hidden" / "x.md").write_text(CAKE)
    (vault / "notes.txt").write_text(CAKE)
    (vault.parent / "README.md").write_text(CAKE)  # outside notes/
    commit()
    assert rag.sync() == rag.SyncStats()
    assert sources() == {"notes/aws-keys.md"}


def test_a_commit_that_touches_no_notes_just_moves_the_marker(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    (vault.parent / "README.md").write_text("hello")
    head = commit()
    assert rag.status().pending == 0 and rag.status().indexed_commit != head
    assert rag.sync() == rag.SyncStats()
    assert Index().indexed_commit() == head


@pytest.mark.parametrize(
    "name",
    [
        "it's a note.md",
        "café notes.md",
        "-dash.md",
        "sub dir/deep note.md",
        'say "hi".md',
    ],
)
def test_unusual_file_names_round_trip(vault, commit, vault_git, name):
    path = vault / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(AWS)
    commit()
    assert rag.sync().indexed == 1 and sources() == {f"notes/{name}"}
    path.write_text(AWS + "\nMore about keys.\n")
    commit()
    assert rag.sync().indexed == 1
    vault_git("rm", "-q", "--", f"notes/{name}")
    commit()
    assert rag.sync().removed == 1 and sources() == set()


# ---- git history moving in other ways --------------------------------------------------------


def test_reset_hard_and_amend_are_followed(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    (vault / "cake.md").write_text(CAKE)
    commit()
    rag.sync()
    assert sources() == {"notes/aws-keys.md", "notes/cake.md"}
    vault_git("reset", "-q", "--hard", "HEAD~1")  # no git hook fires for this
    assert hit_sources("anything") == {"notes/aws-keys.md"}  # a search catches up by itself
    (vault / "aws-keys.md").write_text(AWS.replace("ninety", "sixty"))
    vault_git("add", "-A")
    vault_git("commit", "-q", "--amend", "-m", "amended")
    assert "sixty" in rag.query("how often to rotate keys", 1)[0]["text"]


def test_a_vanished_base_commit_falls_back_to_a_full_resync(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    commit()
    rag.sync()
    Index().set_indexed_commit("0" * 40)  # what a rewritten history looks like
    vault_git("rm", "-q", "notes/cake.md")
    head = commit()
    stats = rag.sync()
    assert stats.indexed == 1 and stats.removed == 1
    assert sources() == {"notes/aws-keys.md"} and Index().indexed_commit() == head


def test_sync_without_commits_or_outside_git_explains_what_to_do(
    vault, tmp_path_factory, monkeypatch
):
    with pytest.raises(git.GitError, match="No 'main' branch"):
        rag.sync()
    outside = tmp_path_factory.mktemp("outside")
    (outside / "notes").mkdir()
    monkeypatch.setattr(config, "ROOT", outside)
    monkeypatch.setattr(config, "NOTES_DIR", outside / "notes")
    with pytest.raises(git.GitError, match="not a git repository"):
        rag.sync()


def test_a_dirty_working_tree_is_never_indexed(vault, commit):
    (vault / "cake.md").write_text(CAKE)
    commit()
    rag.sync()
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    (vault / "aws-keys.md").write_text(AWS.replace("ninety", "sixty"))  # edited after the commit
    rag.sync()
    assert "ninety" in rag.query("how often to rotate keys", 1)[0]["text"]


def test_removing_the_notes_folder_in_a_commit_empties_the_index(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    (vault / "aws-keys.md").unlink()
    commit()
    rag.sync()
    assert sources() == set()


# ---- notes that cannot be indexed -------------------------------------------------------------


def test_empty_title_only_and_unreadable_notes_are_reported_not_indexed(vault, commit):
    (vault / "good.md").write_text(AWS)
    (vault / "empty.md").write_text("")
    (vault / "title-only.md").write_text("# Just a title\n")
    (vault / "bad.md").write_bytes(b"# Bad\n\nbroken \xff\xfe bytes " * 5)
    commit()
    stats = rag.sync()
    assert stats.indexed == 1 and sources() == {"notes/good.md"}
    assert set(stats.failed) == {
        "notes/empty.md",
        "notes/title-only.md",
        "notes/bad.md",
    }
    assert "no content" in stats.failed["notes/empty.md"]


def test_a_note_that_becomes_empty_leaves_no_stale_chunks(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    (vault / "aws-keys.md").write_text("")
    commit()
    stats = rag.sync()
    assert list(stats.failed) == ["notes/aws-keys.md"] and chunk_count() == 0


def test_a_fixed_note_is_indexed_by_the_commit_that_fixes_it(vault, commit):
    (vault / "bad.md").write_bytes(b"# Bad\n\nbroken \xff\xfe bytes " * 5)
    commit()
    assert list(rag.sync().failed) == ["notes/bad.md"]
    (vault / "bad.md").write_text(CAKE)
    commit()
    stats = rag.sync()
    assert stats.indexed == 1 and not stats.failed


def test_oversized_note_is_skipped_and_reported(vault, commit, monkeypatch):
    monkeypatch.setattr(config, "MAX_NOTE_BYTES", 100)
    (vault / "big.md").write_text(AWS)
    (vault / "small.md").write_text("# Small\n\nTiny note.\n")
    commit()
    stats = rag.sync()
    assert stats.indexed == 1 and "larger than" in stats.failed["notes/big.md"]


def test_note_with_utf8_bom_is_indexed(vault, commit):
    (vault / "aws-keys.md").write_bytes(b"\xef\xbb\xbf" + AWS.encode())
    commit()
    assert rag.query("rotate keys", 1)[0]["header_path"] == "AWS Keys > Rotation"


# ---- crashes and consistency ------------------------------------------------------------------


def test_a_sync_interrupted_while_embedding_is_repeated_without_duplicates(
    vault, commit, monkeypatch
):
    for i in range(3):
        (vault / f"note-{i}.md").write_text(AWS.replace("AWS Keys", f"Note {i}"))
    commit()
    real, calls = embeddings.embed_documents, []

    def flaky(texts):
        calls.append(1)
        if len(calls) == 2:
            raise OSError("disk full")
        return real(texts)

    monkeypatch.setattr(embeddings, "embed_documents", flaky)
    with pytest.raises(OSError):
        rag.sync()
    assert Index().indexed_commit() is None  # the marker is written last
    monkeypatch.setattr(embeddings, "embed_documents", real)
    rag.sync()
    assert len(sources()) == 3 and chunk_count() == 3 * PER_NOTE


def test_a_sync_interrupted_before_the_marker_is_repeated_without_duplicates(
    vault, commit, monkeypatch
):
    (vault / "aws-keys.md").write_text(AWS)
    commit()

    def crash(*_args):
        raise OSError("killed")

    with monkeypatch.context() as patch:
        patch.setattr(Index, "set_indexed_commit", crash)
        with pytest.raises(OSError):
            rag.sync()
    assert chunk_count() == PER_NOTE  # the notes were written...
    rag.sync()
    assert chunk_count() == PER_NOTE and Index().indexed_commit()  # ...and a second run replaces


def test_failed_replacement_keeps_the_old_note(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    chunk = Chunk("new text", "AWS Keys", 0)
    with pytest.raises(ValueError):
        Index().replace_notes(
            [EmbeddedNote("notes/aws-keys.md", [chunk, chunk], [[0.0] * config.EMBEDDING_SIZE])]
        )
    assert "Rotate AWS" in rag.query("rotate keys", 1)[0]["text"]


def test_a_missing_table_forgets_the_marker(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    index = Index()
    index._db.drop_table(next(iter(index._db.list_tables().tables)))  # the data is lost
    assert Index().indexed_commit() is None
    assert rag.sync().indexed == 1 and sources() == {"notes/aws-keys.md"}


# ---- configuration ---------------------------------------------------------------------


def test_configuration_change_rebuilds_and_drops_the_old_table_and_marker(
    vault, commit, monkeypatch, embedded
):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    embedded.clear()
    monkeypatch.setattr(config, "FINGERPRINT", "another model or chunk size")
    assert rag.sync().indexed == 1 and embedded
    assert len(Index()._db.list_tables().tables) == 1
    assert (config.DB_DIR / "indexed").read_text().startswith("another model or chunk size")


def test_the_fingerprint_covers_the_settings_and_the_chunker_source():
    settings = (
        config.MODEL,
        config.EMBEDDING_SIZE,
        config.MAX_CHUNK_SIZE,
        config.MIN_CHUNK_SIZE,
        tuple(config.SKIP_HEADERS),
        Path(chunker.__file__).read_bytes(),
    )
    assert hashlib.sha256(repr(settings).encode()).hexdigest() == config.FINGERPRINT


# ---- searching --------------------------------------------------------------------------------


def test_query_returns_best_match_first_with_scores(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    commit()
    hits = rag.query("how often should we rotate credentials", 2)
    assert [h["source"] for h in hits] == ["notes/aws-keys.md"]  # the cake note is far weaker
    assert hits[0]["header_path"] == "AWS Keys > Rotation"
    assert set(hits[0]) == {"text", "source", "header_path", "score"}


def test_query_follows_git_without_a_sync(vault, commit, vault_git):
    (vault / "cake.md").write_text(CAKE)
    commit()
    assert "forty" in rag.query("how long do I bake the cake", 1)[0]["text"]
    (vault / "cake.md").write_text(CAKE.replace("forty", "fifty"))
    commit()
    assert "fifty" in rag.query("how long do I bake the cake", 1)[0]["text"]


def test_query_without_notes_explains_the_problem(vault, commit):
    commit()
    with pytest.raises(ValueError, match="No notes"):
        rag.query("anything")
    with pytest.raises(ValueError, match="empty"):
        rag.query("   ")


def test_query_waits_for_a_running_sync_and_then_sees_its_notes(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    (vault / "cake.md").write_text(CAKE)
    commit()  # new, and another process is about to finish syncing
    holding = threading.Event()

    def other_process():
        with FileLock(config.LOCK_PATH):
            holding.set()
            time.sleep(1.0)

    threading.Thread(target=other_process).start()
    holding.wait()
    started = time.monotonic()
    assert rag.query("bake a cake", 1)[0]["source"] == "notes/cake.md"
    assert time.monotonic() - started >= 0.9


def test_sync_waits_for_a_running_sync(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    holding = threading.Event()

    def other_process():
        with FileLock(config.LOCK_PATH):
            holding.set()
            time.sleep(0.5)

    threading.Thread(target=other_process).start()
    holding.wait()
    started = time.monotonic()
    assert rag.sync().indexed == 1
    assert time.monotonic() - started >= 0.4


# ---- status and the command line --------------------------------------------------------------


def test_status_compares_the_index_with_git(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    head = commit()
    first = rag.status()
    assert (first.pending, first.indexed_commit, first.main_commit) == (1, None, head)
    rag.sync()
    assert rag.status().pending == 0 and rag.status().notes == 1
    (vault / "aws-keys.md").write_text(AWS + "\nMore.\n")  # modified
    (vault / "cake.md").write_text(CAKE)  # added
    commit()
    assert rag.status().pending == 2
    rag.sync()
    vault_git("rm", "-q", "notes/cake.md")  # deleted
    commit()
    assert rag.status().pending == 1 and rag.status().chunks > 0


def run_cli(monkeypatch, capsys, *args):
    monkeypatch.setattr("sys.argv", ["rag", *args])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    captured = capsys.readouterr()
    return exit_info.value.code, captured.out, captured.err


def test_cli_commands_report_clearly(vault, commit, monkeypatch, capsys):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    code, out, _ = run_cli(monkeypatch, capsys, "status")
    assert code == 1 and "1 to update" in out and "index at nothing" in out
    assert "main at " in out  # named after the configured branch
    code, out, _ = run_cli(monkeypatch, capsys, "sync")
    assert code == 0 and "1 indexed" in out
    code, out, _ = run_cli(monkeypatch, capsys, "status")
    assert code == 0 and "0 to update" in out
    code, out, _ = run_cli(monkeypatch, capsys, "query", "how", "to", "rotate", "keys")
    assert code == 0 and "notes/aws-keys.md" in out and "Score:" in out


def test_cli_errors_are_messages_not_tracebacks(vault, commit, monkeypatch, capsys):
    code, _, err = run_cli(monkeypatch, capsys, "query", "anything")
    assert code == 1 and "No 'main' branch" in err and "Traceback" not in err
    commit()
    code, _, err = run_cli(monkeypatch, capsys, "query", "anything")
    assert code == 1 and "No notes to search" in err
    code, out, _ = run_cli(monkeypatch, capsys, "nonsense")
    assert code == 1 and "Usage:" in out
    (vault / "bad.md").write_bytes(b"# Bad\n\nbroken \xff\xfe bytes " * 5)
    commit()
    code, _, err = run_cli(monkeypatch, capsys, "sync")
    assert code == 1 and "skipped notes/bad.md" in err


def test_cli_model_command_prepares_the_model(vault, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(embeddings, "ensure_model", lambda: calls.append("ensured"))
    code, out, _ = run_cli(monkeypatch, capsys, "model")
    assert code == 0 and calls == ["ensured"] and "ready" in out


# ---- keeping the index fast as it grows -------------------------------------------------------


def fragments() -> int:
    return Index()._table.stats()["fragment_stats"]["num_fragments"]


def test_a_big_first_sync_writes_few_data_files(vault, commit, monkeypatch):
    monkeypatch.setattr(config, "WRITE_BATCH_CHUNKS", 40)
    for i in range(60):
        (vault / f"note-{i}.md").write_text(AWS.replace("AWS Keys", f"Note {i}"))
    commit()
    assert rag.sync().indexed == 60
    assert fragments() <= 10  # not one per note


def test_many_small_syncs_are_compacted(vault, commit):
    for i in range(12):  # twelve separate pulls, one new note each
        (vault / f"note-{i}.md").write_text(AWS.replace("AWS Keys", f"Note {i}"))
        commit()
        rag.sync()
    assert fragments() <= 4 and chunk_count() == 12 * PER_NOTE
    assert "Rotate AWS" in rag.query("rotate keys", 1)[0]["text"]


def test_deleted_rows_are_compacted_away(vault, commit, vault_git):
    for i in range(10):
        (vault / f"note-{i}.md").write_text(AWS.replace("AWS Keys", f"Note {i}"))
    commit()
    rag.sync()
    for i in range(6):
        vault_git("rm", "-q", f"notes/note-{i}.md")
    commit()
    assert rag.sync().removed == 6
    assert Index()._table.stats()["num_deleted_rows"] == 0


def test_vector_index_is_built_and_kept_current_as_the_index_grows(vault, commit, monkeypatch):
    monkeypatch.setattr(config, "INDEX_AFTER_ROWS", 4)
    (vault / "aws-keys.md").write_text(AWS * 2)
    (vault / "cake.md").write_text(CAKE * 2)
    commit()
    rag.sync()
    assert Index()._has_vector_index()
    assert rag.query("rotate access keys", 1)[0]["source"] == "notes/aws-keys.md"
    (vault / "vpn.md").write_text(AWS.replace("AWS Keys", "VPN") * 2)
    commit()
    rag.sync()
    assert Index()._table.index_stats(db.VECTOR_INDEX).num_unindexed_rows == 0
    assert "notes/vpn.md" in hit_sources("VPN")


# ---- renames: for git a rename is a delete of the old path plus an add of the new one ---------


def indexed_text(source: str) -> str:
    rows = Index()._table.search().select(["source", "text"]).limit(1000).to_list()
    return "\n".join(row["text"] for row in rows if row["source"] == source)


def test_rename_deletes_the_old_path_and_indexes_the_new_one(vault, commit, vault_git, embedded):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    commit()
    rag.sync()
    embedded.clear()
    vault_git("mv", "notes/aws-keys.md", "notes/aws-credentials.md")
    commit()
    stats = rag.sync()
    assert (stats.indexed, stats.removed) == (1, 1)
    assert sources() == {"notes/aws-credentials.md", "notes/cake.md"}
    assert "Rotate AWS" in indexed_text("notes/aws-credentials.md")
    assert embedded and all("AWS Keys" in text for text in embedded)  # only the renamed note
    assert chunk_count() == 2 * PER_NOTE  # nothing doubled


def test_rename_with_edits_is_still_a_delete_and_an_add(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    vault_git("mv", "notes/aws-keys.md", "notes/aws-credentials.md")
    (vault / "aws-credentials.md").write_text(AWS.replace("ninety", "sixty"))
    commit()
    assert rag.sync().removed == 1
    assert sources() == {"notes/aws-credentials.md"}
    assert "sixty" in indexed_text("notes/aws-credentials.md")


def test_case_only_rename_leaves_no_duplicate_even_on_a_case_insensitive_file_system(
    vault, commit, vault_git
):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    vault_git("mv", "notes/aws-keys.md", "notes/AWS-KEYS.md")
    commit()
    stats = rag.sync()
    assert (stats.indexed, stats.removed) == (1, 1)
    assert sources() == {"notes/AWS-KEYS.md"} and chunk_count() == PER_NOTE


def test_renaming_a_folder_moves_every_note_in_it(vault, commit, vault_git):
    (vault / "old").mkdir()
    for name in ("one", "two", "three"):
        (vault / "old" / f"{name}.md").write_text(AWS.replace("AWS Keys", name.title()))
    commit()
    rag.sync()
    vault_git("mv", "notes/old", "notes/new")
    commit()
    stats = rag.sync()
    assert (stats.indexed, stats.removed) == (3, 3)
    assert sources() == {f"notes/new/{name}.md" for name in ("one", "two", "three")}


def test_swapping_two_notes_swaps_their_content(vault, commit, vault_git):
    (vault / "a.md").write_text(AWS)
    (vault / "b.md").write_text(CAKE)
    commit()
    rag.sync()
    vault_git("mv", "notes/a.md", "notes/tmp.md")
    vault_git("mv", "notes/b.md", "notes/a.md")
    vault_git("mv", "notes/tmp.md", "notes/b.md")
    commit()
    rag.sync()
    assert "Rotate AWS" in indexed_text("notes/b.md") and "chocolate" in indexed_text("notes/a.md")


def test_moving_a_note_out_of_notes_removes_it_and_into_notes_adds_it(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    (vault.parent / "draft.md").write_text(CAKE)
    commit()
    rag.sync()
    vault_git("mv", "notes/aws-keys.md", "archive.md")
    vault_git("mv", "draft.md", "notes/cake.md")
    commit()
    stats = rag.sync()
    assert (stats.indexed, stats.removed) == (1, 1)
    assert sources() == {"notes/cake.md"}


def test_moving_a_note_into_a_hidden_folder_removes_it(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / ".trash").mkdir()
    commit()
    rag.sync()
    vault_git("mv", "notes/aws-keys.md", "notes/.trash/aws-keys.md")
    commit()
    assert rag.sync().removed == 1 and sources() == set()


def test_git_decides_not_the_file_system(vault, commit, vault_git):
    """What is indexed is the committed note, whatever happens to the file afterwards."""
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    commit()
    rag.sync()
    (vault / "aws-keys.md").write_text(AWS.replace("ninety", "sixty"))
    commit()
    (vault / "aws-keys.md").unlink()  # deleted locally, not committed
    stats = rag.sync()
    assert stats.indexed == 1 and not stats.failed
    assert "sixty" in rag.query("how often to rotate keys", 1)[0]["text"]


# ---- the index is main, whichever branch is checked out ---------------------------------------


def test_commits_on_a_feature_branch_never_change_the_index(vault, commit, vault_git, embedded):
    (vault / "aws-keys.md").write_text(AWS)
    main_head = commit()
    rag.sync()
    embedded.clear()
    vault_git("checkout", "-q", "-b", "feature/new-note")
    (vault / "cake.md").write_text(CAKE)
    commit("my new note")
    assert rag.sync() == rag.SyncStats()
    assert sources() == {"notes/aws-keys.md"} and Index().indexed_commit() == main_head
    assert hit_sources("how long do I bake the cake") == {"notes/aws-keys.md"}
    assert embedded == [] or not any("Cake" in text for text in embedded)


def test_edits_deletes_and_renames_on_a_branch_do_not_touch_the_index(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "cake.md").write_text(CAKE)
    commit()
    rag.sync()
    before = indexed_text("notes/aws-keys.md")
    vault_git("checkout", "-q", "-b", "feature/changes")
    (vault / "aws-keys.md").write_text(AWS.replace("ninety", "sixty"))
    vault_git("rm", "-q", "notes/cake.md")
    commit()
    vault_git("mv", "notes/aws-keys.md", "notes/renamed.md")
    commit()
    rag.sync()
    rag.query("anything")
    assert sources() == {"notes/aws-keys.md", "notes/cake.md"}
    assert indexed_text("notes/aws-keys.md") == before


def test_a_note_becomes_searchable_once_it_is_merged_into_main(vault, commit, vault_git, embedded):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    vault_git("checkout", "-q", "-b", "feature/new-note")
    (vault / "cake.md").write_text(CAKE)
    commit("my new note")
    vault_git("checkout", "-q", "main")  # nothing new on main
    assert rag.sync().indexed == 0 and sources() == {"notes/aws-keys.md"}
    vault_git("merge", "-q", "--no-ff", "-m", "approved", "feature/new-note")  # the PR is merged
    embedded.clear()
    stats = rag.sync()
    assert (stats.indexed, stats.removed) == (1, 0)
    assert sources() == {"notes/aws-keys.md", "notes/cake.md"}
    assert embedded and all("Cake" in text for text in embedded)


def test_what_main_gains_is_picked_up_from_any_branch(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    rag.sync()
    vault_git("checkout", "-q", "-b", "feature/work")
    vault_git("checkout", "-q", "main")
    (vault / "cake.md").write_text(CAKE)  # a teammate's approved note arrives on main
    commit("approved")
    vault_git("checkout", "-q", "feature/work")
    assert rag.sync().indexed == 1 and sources() == {"notes/aws-keys.md", "notes/cake.md"}


def test_searching_on_a_branch_reads_main_not_the_branch(vault, commit, vault_git):
    (vault / "cake.md").write_text(CAKE)
    commit()
    vault_git("checkout", "-q", "-b", "feature/edit")
    (vault / "cake.md").write_text(CAKE.replace("forty", "fifty"))
    commit()
    hit = rag.query("how long do I bake the cake", 1)[0]  # the first index is built from main too
    assert "forty" in hit["text"] and "fifty" not in hit["text"]


def test_a_detached_head_changes_nothing(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    head = commit()
    (vault / "cake.md").write_text(CAKE)
    commit()
    vault_git("checkout", "-q", "--detach", head)
    assert rag.sync().indexed == 2 and sources() == {"notes/aws-keys.md", "notes/cake.md"}


def test_with_no_default_branch_the_error_says_how_to_fix_it(vault, commit, vault_git):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    vault_git("branch", "-m", "main", "trunk")
    with pytest.raises(git.GitError, match="BRAIN_BRANCH"):
        rag.sync()


def test_the_indexed_branch_can_be_set(vault, commit, vault_git, monkeypatch):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    vault_git("branch", "trunk")
    monkeypatch.setattr(config, "BRANCH", "trunk")
    assert rag.sync().indexed == 1


def test_status_and_cli_work_from_a_branch(vault, commit, vault_git, monkeypatch, capsys):
    (vault / "aws-keys.md").write_text(AWS)
    commit()
    vault_git("checkout", "-q", "-b", "feature/x")
    (vault / "cake.md").write_text(CAKE)
    commit()
    assert (rag.status().pending, rag.status().indexed_commit) == (1, None)
    code, out, _ = run_cli(monkeypatch, capsys, "status")
    assert code == 1 and "0 notes indexed" in out and "1 to update" in out
    code, out, _ = run_cli(monkeypatch, capsys, "sync")
    assert code == 0 and "1 indexed" in out
    code, out, _ = run_cli(monkeypatch, capsys, "status")
    assert code == 0 and "1 notes indexed" in out and "0 to update" in out


# ---- how many results a query returns ---------------------------------------------------------


def hit(source, score):
    return {"source": source, "score": score, "text": "", "header_path": ""}


def test_results_far_below_the_best_match_are_dropped():
    hits = [hit("a", 0.90), hit("b", 0.85), hit("c", 0.60), hit("d", 0.55)]
    assert [h["source"] for h in rag._close_to_best(hits)] == ["a", "b"]


def test_every_close_chunk_is_kept_even_from_the_same_note():
    hits = [hit("a", 0.9), hit("a", 0.89), hit("a", 0.88), hit("b", 0.87)]
    assert [h["source"] for h in rag._close_to_best(hits)] == ["a", "a", "a", "b"]


def test_the_best_match_is_always_returned_however_weak():
    assert rag._close_to_best([hit("a", -0.3)]) == [hit("a", -0.3)]


def test_query_returns_at_most_n_results(vault, commit):
    for i in range(6):
        (vault / f"aws-{i}.md").write_text(AWS.replace("AWS Keys", f"AWS Keys {i}"))
    commit()
    assert len(rag.query("how often to rotate keys", 3)) == 3


def test_query_returns_several_notes_when_several_match(vault, commit):
    (vault / "aws-keys.md").write_text(AWS)
    (vault / "aws-rotation.md").write_text(AWS.replace("AWS Keys", "Key Rotation"))
    (vault / "cake.md").write_text(CAKE)
    commit()
    found = [h["source"] for h in rag.query("how often to rotate keys")]
    assert {"notes/aws-keys.md", "notes/aws-rotation.md"} <= set(found)
