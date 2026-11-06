"""brain.toml: the settings a team chooses, shared by every developer and every process."""

import subprocess
import sys
from pathlib import Path

import pytest

from rag import config

REPO = Path(config.__file__).resolve().parents[1]


def settings(tmp_path, text: str) -> dict:
    path = tmp_path / "brain.toml"
    path.write_text(text)
    return config.load_team_settings(path)


def test_without_a_file_the_defaults_apply(tmp_path):
    assert config.load_team_settings(tmp_path / "brain.toml") == config._TEAM_DEFAULTS


def test_an_empty_file_keeps_every_default(tmp_path):
    assert settings(tmp_path, "") == config._TEAM_DEFAULTS


def test_a_team_can_change_the_branch_and_the_skipped_headings(tmp_path):
    result = settings(tmp_path, 'branch = "master"\nskip_headings = ["Links"]\n')
    assert (result["branch"], result["skip_headings"]) == ("master", ["Links"])


def test_setting_only_one_value_keeps_the_other_default(tmp_path):
    result = settings(tmp_path, 'branch = "trunk"')
    assert result["branch"] == "trunk"
    assert result["skip_headings"] == config._TEAM_DEFAULTS["skip_headings"]


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('brnach = "main"', r"unknown setting \['brnach'\]"),
        ("branch = main", "not valid TOML"),
        ("branch = 3", "`branch` is a name"),
        ('branch = ""', "`branch` is a name"),
        ('skip_headings = "References"', "`skip_headings` is a list"),
        ("skip_headings = [1, 2]", "`skip_headings` is a list"),
    ],
)
def test_a_mistake_in_the_file_is_a_clear_error_not_silently_ignored(tmp_path, text, message):
    with pytest.raises(RuntimeError, match=message):
        settings(tmp_path, text)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("max_results = 0", "`max_results`"),
        ("max_results = 2.5", "`max_results`"),
        ("max_results = true", "`max_results`"),
        ("score_margin = 0", "`score_margin`"),
        ("score_margin = 1.5", "`score_margin`"),
        ('score_margin = "wide"', "`score_margin`"),
        ("max_chunk_size = 300", "`max_chunk_size`"),
        ("max_chunk_size = 90000", "`max_chunk_size`"),
        ("min_chunk_size = 0", "`min_chunk_size`"),
        ("max_chunk_size = 600\nmin_chunk_size = 400", "`min_chunk_size`"),
    ],
)
def test_numbers_outside_what_the_chunker_and_search_handle_are_refused(tmp_path, text, message):
    with pytest.raises(RuntimeError, match=message):
        settings(tmp_path, text)


def test_a_team_can_tune_search_and_chunk_sizes(tmp_path):
    result = settings(
        tmp_path,
        "max_results = 5\nscore_margin = 0.2\nmax_chunk_size = 2000\nmin_chunk_size = 300\n",
    )
    assert result["max_results"] == 5 and result["score_margin"] == 0.2
    assert (result["max_chunk_size"], result["min_chunk_size"]) == (2000, 300)


def test_the_committed_file_says_what_the_defaults_say():
    assert config.load_team_settings(REPO / "brain.toml") == config._TEAM_DEFAULTS


def python(code: str, env: dict) -> str:
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=REPO, env=env, check=True
    )
    return result.stdout.strip()


def test_the_environment_variable_overrides_the_file_for_one_person(monkeypatch):
    import os

    base = {k: v for k, v in os.environ.items() if k != "BRAIN_BRANCH"}
    show = "from rag import config; print(config.BRANCH)"
    assert python(show, base) == "main"
    assert python(show, {**base, "BRAIN_BRANCH": "trunk"}) == "trunk"
    assert python(show, {**base, "BRAIN_BRANCH": ""}) == "main"  # empty means not set
