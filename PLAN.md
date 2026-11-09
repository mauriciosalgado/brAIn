# brAIn plan

Goal: a team knowledge vault (Markdown in `notes/`) that humans browse and AI agents search, with the
index local to each developer. No servers.

Rules: keep it simple · measure before adding · nothing is committed without the owner's OK.

## Done

- [x] Note standards, templates, runbooks keep state in `/tmp` (`STANDARDS.md`, `templates/`)
- [x] Chunker: one chunk per heading (`rag/index/chunker.py`); long sections are split at paragraph, line or word
      breaks. Checked on a 70-note team vault + 12 messy notes (`tests/fixtures/`): size limit, no text lost
- [x] Embedder: arctic-embed-m-v2.0 int8 (multilingual, Apache-2.0, 320 MB, registered as a fastembed custom model), small batches, query prefix, model cached in `.rag/models`, repaired by `rag model`
- [x] Local index: LanceDB in `.rag/`, exact scan below 50k chunks, IVF-HNSW above
- [x] Index follows git: what git reports as A / M / D since the last indexed commit is indexed / re-indexed /
      removed (`rag/git.py` plans; `rag/index/indexer.py` applies); one marker (the commit) says if the index is fresh
- [x] Git flow: `.githooks/` + `setup.sh` + `doctor.sh`; sync updates the index, while CLI/MCP
      use `store.open_index` and retrieval-only `search.query` without checking Git
- [x] Notes with no content (empty, title only) or unreadable are reported, never silently skipped
- [x] Tokenizer uses the model's 8,192-token context; over-limit input is reported before inference,
      and the context limit is part of the index fingerprint
- [x] MCP tool `search_notes` (bounded `k`, clear errors) and CLI `rag sync | query | status | model`
- [x] Historical scale measurements: 200,000 chunks (5 ms search; 1.8 GB on disk); 20,000 notes: a pull of 15 changed
      notes syncs in 0.1 s; 273 tests. First index costs about 22 ms per chunk (100k chunks is about 35 min)

## Next (in order)

Bugs found in review (confirmed by running them):

- [x] Case-only rename (`aws-keys.md` → `AWS-KEYS.md`) leaves both paths in the index on macOS: decide
      added/deleted from git's A/D/M letter, not from `is_file()`
- [x] Failed notes were never retried: notes are now read from the commit, so failures are
      deterministic and a fixing commit retries them
- [x] `requires-python` is `>=3.11,<3.14` (`onnxruntime` has no 3.10 wheel)

Then:

- [x] Commit the reviewed and validated simplified baseline
- [x] `README.md` and `AGENTS.md`: what it is, 3-command setup, MCP config, how to write a note
- [ ] CI: pytest, ruff, shellcheck on Python 3.11-3.13 (the model must be downloaded first)
- [ ] `rag eval`: run labelled questions (`tests/fixtures/team-vault/gold.json`, 85 of them) against the index
      and print hit@k / MRR, so any change to model, chunking or margin is measured, not guessed
- [ ] Re-tune chunk size (1000 chars) for the current model, and the 0.10 score margin, with `rag eval`
- [ ] Exact-identifier boost (`aws-rds-copy`, error codes, flags): BM25 hybrid gave no gain on paraphrased
      questions, but identifier queries were not measured
- [x] MCP `search_notes` returns plain text: one `<passage rank source section>` block per chunk, text unescaped
- [x] MCP `read_note(path)`: current Markdown files through `notes.read_note`, with shared path rules
- [ ] MCP `list_notes(folder)`
- [x] `brain.toml`: the settings a user may change (branch, skipped folders and headings, result count, score
      margin, chunk sizes), commented in plain words, read at run time and validated; `BRAIN_BRANCH` is a
      personal override. The model and vector size stay in code on purpose.
- [x] MCP search never builds an index: missing or unusable caches ask for explicit synchronization
- [x] Agent authoring help: MCP tools `get_note_standards` and `get_note_template`
- [ ] Peak memory of a query is 1.35 GB (multilingual vocabulary): check whether it can come down
- [ ] Measure German retrieval (the model is multilingual, but untested on German notes)

## Later / parked

- [ ] Quality gate (`rag lint` / CI): no empty notes, `STANDARDS.md` naming, folder, tags, no secrets
- [ ] Stale-note detection; usage logging to find missing docs
- [ ] Remove real AWS account ID and company hostnames from the public repo
- [ ] Tell users that search results go to the AI host's model, so notes must hold no secrets
- [ ] Windows support (scripts are `sh`; untested)
- [ ] Shared index for a very large team (LanceDB on object storage), only if needed

## Decisions

- Store: LanceDB (embedded). Rejected: SQLite+NumPy (no vector index, slow at scale), Chroma (not
  process-safe), FAISS (library only), Qdrant (embedded mode is dev-only; server needs a container).
- Types are tags for humans; search never depends on them.
- Works for one person or a team: publish on the configured remote branch, then sync its last known
  commit. Docs and tools say "your notes", not "the team's".
- Instructions have one home each: the MCP tool descriptions (how to use the tools), `STANDARDS.md` (the
  rules, served by `get_note_standards`), `AGENTS.md` (working in the repo), and
  `.github/copilot-instructions.md`, which only points to `AGENTS.md`. Written after GitHub's custom
  instructions docs, agents.md and Anthropic's "Writing tools for agents".
- A batch of notes is replaced in one atomic `merge_insert`: a search sees the old chunks or the new
  ones, never a note with none, and each batch makes one version instead of two.
- The index follows the configured remote-tracking branch (`origin/main` by default), whichever
  branch is checked out. Unpushed commits are never indexed. A rename is a delete + add.
  Hooks normally sync after push/fetch/pull; a missed or failed sync requires `rag sync`.
  Search opens the existing index and holds its lock through retrieval. It never checks Git,
  synchronizes, or rebuilds missing/incompatible caches.
- Sync reads published notes from the commit (`git cat-file`). Whole-note reads use current files
  through `notes.read_note`, so they may show newer edits than search. The read implementation is
  isolated from MCP and search so its source can change later without changing callers.
- One marker file in `.rag/` holds the settings fingerprint and the last indexed commit. Different
  settings (model, chunk size, the chunker's code) or a lost table rebuild the index during sync,
  not during inspection. The marker is cleared before changing notes, so interrupted batches
  cannot claim to match a commit.
- After pulling code changes, restart the MCP server (restart your AI tool): a process with an old
  fingerprint can reject a freshly synced cache. Retrieval does not rebuild it automatically.
- Queries return every chunk (not note) within `score_margin` (0.10) of the best, up to `max_results` (10); the best is always kept.
  Model choice, measured on a 353-chunk mock vault (70 notes, 85 questions, near-duplicate topics):
  arctic-embed-m-v2.0 has the best recall (hit@5 0.88, MRR 0.69) vs bge-small (0.71, 0.56) and
  arctic-m v1 (0.83, 0.68); it is also faster (int8) and multilingual. Qwen3-Embedding-0.6B has the
  best hit@1 (0.66) but lower hit@5 (0.78), is 2x slower and needs a custom ONNX runtime. EmbeddingGemma
  has a non-Apache license. Rejected: per-note cap (hurts recall), BM25 hybrid (no gain on paraphrased
  questions), absolute score floor (kills recall), cross-encoder reranker (+0.04 MRR, 145 ms/query).
  Vectors are kept at the model's full 768 dimensions: truncating to 256 saved 3x disk for 0.02 of hit@5, which was not worth numpy and a second margin. Memory is 1.4 GB per process whatever the file or session setting (measured). Chunk size (1000 chars) was not re-tuned for this model: a candidate for `rag eval`.
