from __future__ import annotations

import os
import importlib
from shutil import which

from devenv.constants import SYSTEM_MACHINE, homebrew_bin, home, root
from devenv.lib import brew, config, gcloud, proc, tenv, uv, venv

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

    proc.run(
        (f"{homebrew_bin}/brew", "bundle"),
        cwd=reporoot,
    )

    try:
        proc.run(
            ("helm", "plugin", "install", "https://github.com/databus23/helm-diff", "--verify=false"),
            cwd=reporoot,
            stdout=True
        )
    except RuntimeError as e:
        if "Error: plugin already exists" not in str(e): # Sad workaround since there's no way to ignore this in helm
            raise SystemExit(e)

    gcloud.install(
        cfg["gcloud"]["version"],
        cfg["gcloud"][SYSTEM_MACHINE],
        cfg["gcloud"][f"{SYSTEM_MACHINE}_sha256"],
        reporoot,
    )

    install_gcloud_kubectl(f"{reporoot}/.devenv/bin/gcloud")

    ensure_gcloud_authed(f"{reporoot}/.devenv/bin/gcloud")

    tenv.install(
        cfg["tenv"]["version"],
        cfg["tenv"][SYSTEM_MACHINE],
        cfg["tenv"][f"{SYSTEM_MACHINE}_sha256"],
        reporoot,
    )

    for name in ("sentry-kube", "salt"):
        venv_dir, python_version, requirements, editable_paths, bins = venv.get(reporoot, name)
        url, sha256 = config.get_python(reporoot, python_version)
        print(f"ensuring {name} venv at {venv_dir}...")
        venv.ensure(venv_dir, python_version, url, sha256)

        print(f"syncing {name} with {requirements}...")
        venv.sync(reporoot, venv_dir, requirements, editable_paths, bins)

    need_cluster_credentials = True

    if os.path.exists(f"{home}/.kube/config"):
        with open(f"{home}/.kube/config", "r") as f:
            for line in f:
                if "zdpwkxst" in line:
                    need_cluster_credentials = False
                    break

    if need_cluster_credentials:
        proc.run(("bin/gke-credentials-setup",), cwd=reporoot)

    return 0
