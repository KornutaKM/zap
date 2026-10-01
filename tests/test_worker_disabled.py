import os
import subprocess
import sys


def test_disabled_worker_does_not_require_bot_token():
    env = os.environ.copy()
    env.pop("BOT_TOKEN", None)
    env["PRICE_ALERTS_ENABLED"] = "false"

    result = subprocess.run(
        [sys.executable, "-m", "app.worker"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
