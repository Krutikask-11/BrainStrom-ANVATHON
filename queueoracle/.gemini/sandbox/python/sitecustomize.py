"""Sandbox Python startup hook, auto-imported by `site` via PYTHONPATH.

Ignores WaitNamedPipe's spurious ERROR_FILE_NOT_FOUND in a Windows sandbox.
"""

import os

if os.name == "nt":
  import _winapi  # pylint: disable=g-import-not-at-top  # Windows only

  _original_wait_named_pipe = _winapi.WaitNamedPipe

  def _wait_named_pipe(name, timeout):
    """Like _winapi.WaitNamedPipe, but ignores ERROR_FILE_NOT_FOUND."""
    try:
      _original_wait_named_pipe(name, timeout)
    except FileNotFoundError:
      pass
  _winapi.WaitNamedPipe = _wait_named_pipe
