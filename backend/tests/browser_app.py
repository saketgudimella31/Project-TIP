"""TEST ONLY: a synthetic gateway for deterministic browser checks.

Never use this app as the production entry point. Production uses
tip.app:create_app and the real configured gateway, with no synthetic fallback.
"""
import tempfile
from pathlib import Path

from tip.app import create_app
from tip.config import Settings

from .fixtures import sample_result

directory = tempfile.TemporaryDirectory(prefix="tip-browser-test-")
app = create_app(Settings(
    _env_file=None, data_dir=Path(directory.name),
    gateway_url="https://synthetic-test.invalid/completions",
))


class SyntheticGateway:
    def analyze(self, target, context, artifacts, coverage=None):
        return sample_result(target, context, artifacts)


app.state.manager.gateway = SyntheticGateway()