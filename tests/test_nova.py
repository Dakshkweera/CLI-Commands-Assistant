"""
tests/test_nova.py

Automated checks for nova's pure logic functions.
Run them all from the project folder with:  pytest

Each test is one "given this input, I expect this result". pytest finds every
function named test_* and runs it; `assert` is the check (fails if it's False).
"""

import os

from nova.__main__ import (
    _split_leading_cd,
    _resolve_cd,
    _looks_like_network_error,
    _looks_like_bad_key,
    _looks_like_quota,
)
from nova.memory import Memory


# ---- Compound cd splitting -------------------------------------------------

def test_cd_splits_off_the_rest():
    # A compound command splits into the cd part + the rest.
    assert _split_leading_cd('cd "System design"; explorer .') == (
        'cd "System design"', 'explorer .'
    )


def test_plain_cd_has_no_rest():
    # Just a cd, nothing after it — the "rest" is empty.
    assert _split_leading_cd('cd ..') == ('cd ..', '')


def test_semicolon_inside_quotes_is_not_split():
    # The ; is inside quotes, so it must NOT be treated as a separator.
    assert _split_leading_cd('cd "a; b"') == ('cd "a; b"', '')


def test_double_ampersand_also_splits():
    # `&&` works as a separator too, not just `;`.
    assert _split_leading_cd('cd Docs && dir') == ('cd Docs', 'dir')


# ---- cd resolution ---------------------------------------------------------

def test_cd_tilde_expands_to_home():
    # `cd ~` must resolve to the user's home folder, not a folder named "~".
    folder, ok, error = _resolve_cd("C:\\", "cd ~")
    assert ok is True
    assert folder == os.path.abspath(os.path.expanduser("~"))


def test_cd_missing_folder_reports_error():
    # A folder that doesn't exist → ok is False and a clear error message.
    folder, ok, error = _resolve_cd(os.path.expanduser("~"), "cd no-such-folder-xyz")
    assert ok is False
    assert "no such folder" in error


# ---- Error classification --------------------------------------------------

def test_dns_error_is_network():
    error = Exception('[Errno 11001] getaddrinfo failed')
    assert _looks_like_network_error(error) is True


def test_bad_key_message_is_detected():
    error = Exception('API key not valid. Please pass a valid API key.')
    assert _looks_like_bad_key(error) is True


def test_quota_message_is_detected():
    error = Exception('429 RESOURCE_EXHAUSTED. Resource has been exhausted.')
    assert _looks_like_quota(error) is True


# ---- Session memory --------------------------------------------------------

def test_last_failure_finds_the_failed_command():
    m = Memory()
    m.record('dir', 'ok output', '', 0)            # a success (exit code 0)
    m.record('bad-cmd', '', 'not recognized', 1)   # a failure (exit code 1)
    assert m.last_failure()['command'] == 'bad-cmd'


def test_last_failure_is_none_when_all_ok():
    m = Memory()
    m.record('dir', 'ok', '', 0)
    assert m.last_failure() is None
