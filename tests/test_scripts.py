"""Tests for common.sh, the helper sourced by the shell scripts."""

import os
import subprocess
from pathlib import Path

import pytest
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
COMMON = REPO / 'common.sh'


def run_zsh(snippet: str, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    full_env = {k: v for k, v in os.environ.items() if k != 'PYTHON'}
    if env:
        full_env.update(env)
    return subprocess.run(
        ['/bin/zsh', '-c', f'source "{COMMON}"; {snippet}'],
        capture_output=True, text=True, env=full_env, cwd=REPO,
    )


@pytest.mark.unit
class TestResolvePython:
    def test_picks_an_interpreter_that_has_paho(self):
        result = run_zsh('resolve_python && "$PYTHON" -c "import paho.mqtt.client"')
        assert result.returncode == 0, result.stderr

    def test_honours_explicit_python_that_has_paho(self):
        result = run_zsh('resolve_python && echo "$PYTHON"', env={'PYTHON': '/usr/bin/python3'})
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == '/usr/bin/python3'

    def test_fails_loud_when_explicit_python_lacks_paho(self):
        result = run_zsh('resolve_python', env={'PYTHON': '/bin/false'})
        assert result.returncode != 0
        assert 'paho' in (result.stdout + result.stderr).lower()


@pytest.mark.unit
class TestProcessPatterns:
    """pgrep patterns must match whichever interpreter path start.sh resolved."""

    def test_patterns_match_absolute_interpreter(self):
        import re
        result = run_zsh('echo "$WALDO_PATTERN"; echo "$FOUND_HIM_PATTERN"')
        assert result.returncode == 0, result.stderr
        waldo_pat, found_pat = result.stdout.strip().splitlines()
        assert re.search(waldo_pat, '/usr/bin/python3 ./waldo.py --broker x')
        assert re.search(waldo_pat, '/opt/homebrew/bin/python3.13 ./waldo.py')
        # /usr/bin/python3 re-execs as the framework binary, capital P, as ps shows it
        assert re.search(waldo_pat, '/Library/Developer/CommandLineTools/Library/Frameworks/Python3.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python ./waldo.py --broker x')
        assert not re.search(waldo_pat, 'tail -F waldo.py.log')
        assert re.search(found_pat, '/usr/bin/python3 ./found-him.py studio')


@pytest.mark.unit
class TestResolveRealHome:
    def test_rejects_profile_dir(self):
        result = run_zsh('resolve_real_home', env={'HOME': '/Users/nobody/.claude-profiles/x'})
        # Either resolves the real home via dscl, or refuses; it must never echo the profile dir.
        assert '.claude-profiles' not in result.stdout
