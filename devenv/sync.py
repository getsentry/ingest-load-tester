from __future__ import annotations

import os
import importlib
from shutil import which

from devenv.constants import SYSTEM_MACHINE, homebrew_bin, home, root
from devenv.lib import brew, config, gcloud, proc, uv, venv

def install_gcloud_kubectl(gcloud: str) -> None:
    if which("kubectl") is None:
        print("installing kubectl...")
        proc.run((gcloud, "components", "install", "-q", "--verbosity=error", "kubectl"))
    else:
        print("kubectl already installed, skipping install step...")


def ensure_gcloud_authed(gcloud: str) -> None:
    # gcloud auth list --filter=status:ACTIVE --format="value(account)"
    # should return a sentry.io email.
    # if no accounts exist or are active, stdout shouldnt have anything (rc is still 0).

    # A faster way to check is gcloud config config-helper,
    # which exits 1 if there is no active account,
    # and also prompts for yubikey 2FA if it needs refreshing.
    try:
        proc.run(
            (
                gcloud,
                "config",
                "config-helper",
            ),
            stdout=True,
        )
        return
    except RuntimeError:
        proc.run(
            (
                gcloud,
                "auth",
                "login",
                "--activate",
                "--update-adc",
            ),
        )

    # Check again, and if something's still wrong then exit.
    proc.run(
        (
            gcloud,
            "config",
            "config-helper",
        ),
        exit=True,
    )


def check_minimum_version(minimum_version: str):
    version = importlib.metadata.version("sentry-devenv")

    parsed_version = tuple(map(int, version.split(".")))
    parsed_minimum_version = tuple(map(int, minimum_version.split(".")))

    if parsed_version < parsed_minimum_version:
        raise SystemExit(
            f"""
Hi! To reduce potential breakage we've defined a minimum
devenv version ({minimum_version}) to run sync.

Please run the following to update your global devenv:

devenv update

Then, use it to run sync this one time.

{root}/bin/devenv sync
"""
        )


def main(context: dict[str, str]) -> int:
    check_minimum_version("1.14.2")

    reporoot = context["reporoot"]

    # configure versions for tools in devenv/config.ini
    cfg = config.get_repo(reporoot)

    uv.install(
        cfg["uv"]["version"],
        cfg["uv"][SYSTEM_MACHINE],
        cfg["uv"][f"{SYSTEM_MACHINE}_sha256"],
        reporoot,
    )

    brew.install()

    gcloud.install(
        cfg["gcloud"]["version"],
        cfg["gcloud"][SYSTEM_MACHINE],
        cfg["gcloud"][f"{SYSTEM_MACHINE}_sha256"],
        reporoot,
    )

    ensure_gcloud_authed(f"{reporoot}/.devenv/bin/gcloud")

    return 0
