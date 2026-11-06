"""brain.toml: the settings a user may change."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from rag import config

REPO = Path(config.__file__).resolve().parents[1]


def load(tmp_path, text: str) -> config.Settings:
    path = tmp_path / "brain.toml"
    path.write_text(text)
    return config.load_settings(path)


def test_without_a_file_or_with_an_empty_one_every_default_applies(tmp_path):
    assert config.load_settings(tmp_path / "brain.toml") == config.Settings()
    assert load(tmp_path, "") == config.Settings()


def test_settings_can_be_changed_one_at_a_time(tmp_path):
    result = load(tmp_path, 'branch = "master"\nskip_folders = ["archive"]\nmax_results = 5\n')
    assert (result.branch, result.skip_folders, result.max_results) == ("master", ["archive"], 5)
    assert result.max_chunk_size == config.Settings().max_chunk_size


@pytest.mark.parametrize(
    ("text", "setting"),
    [
        ('brnach = "main"', "brnach"),
        ('branch = ""', "branch"),
        ("branch = 3", "branch"),
        ('skip_folders = "archive"', "skip_folders"),
        ("max_results = 0", "max_results"),
        ("max_results = 2.5", "max_results"),
        ("max_results = true", "max_results"),
        ("score_margin = 1.5", "score_margin"),
        ("max_chunk_size = 300", "max_chunk_size"),
        ("max_chunk_size = 600\nmin_chunk_size = 400", "min_chunk_size"),
    ],
)
def test_a_mistake_is_a_clear_error_that_names_the_setting(tmp_path, text, setting):
    with pytest.raises(RuntimeError, match=f"brain.toml: .*{setting}"):
        load(tmp_path, text)


def test_a_file_that_is_not_toml_is_a_clear_error(tmp_path):
    with pytest.raises(RuntimeError, match="not valid TOML"):
        load(tmp_path, "branch = main")


def test_the_committed_file_says_what_the_defaults_say():
    assert config.load_settings(REPO / "brain.toml") == config.Settings()


def test_the_environment_variable_overrides_the_file_for_one_checkout():
    base = {name: value for name, value in os.environ.items() if name != "BRAIN_BRANCH"}

    def branch(env: dict) -> str:
        code = "from rag import config; print(config.BRANCH)"
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            cwd=REPO,
            env=env,
            check=True,
        )
        return result.stdout.strip()

    assert branch(base) == "main"
    assert branch({**base, "BRAIN_BRANCH": "trunk"}) == "trunk"
    assert branch({**base, "BRAIN_BRANCH": ""}) == "main"
