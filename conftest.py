# Root conftest: mock GObject introspection so tests run without native gi libraries.
# This allows the test suite to run in environments where python-gobject is not installed
# (e.g. CI containers, Arch Linux without gobject-introspection).
import sys
from unittest import mock

if "gi" not in sys.modules:
    gi_mock = mock.MagicMock()
    sys.modules["gi"] = gi_mock
    sys.modules["gi.repository"] = gi_mock
    sys.modules["gi.repository.GLib"] = gi_mock
