#!/usr/bin/env python3
"""Build the portal: each available site (module or release), then the root.

    python3 tools/site/build.py [--release PATH] [--strict] [--skip-vendor]
    python3 tools/site/build.py --serve [--release PATH] [--dev-addr HOST:PORT]

Steps of a build (`make docs-build` runs this script, then check_site.py):

1. prebuild.py: the vendored Mermaid bundle and docs/<path>/assets/data/updates.json;
2. for each available site of academy.toml (or the one given with
   --release, a path such as day2/2024.1): write its configuration and run
   `zensical build` into site/<path>/;
3. write the docs and the configuration of the root site (learning path,
   home of the versioned module, not-found page, one page per planned module
   or release), build it into .build/root/site/ and copy it into site/, with
   versions.json, the sitemap index and, when SITE_DOMAIN is set, CNAME.

The address of the portal is https://<SITE_DOMAIN>/ when that environment
variable is set, `site_url` of zensical.base.toml otherwise.

Without --release the output directory is emptied first, so that nothing is
left of a site that was removed from the registry. With --release the other
sites are left as they are.

--serve starts the live preview of Zensical for one site (the default
release unless --release is given). The preview serves that site only: links
to other sites do not work there. To look at the whole portal, build it and
run tools/site/serve_site.py.

Zensical is run with the interpreter that runs this script, and with
tools/site on PYTHONPATH so that the local Markdown extension (portal_mdx) is
found.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prebuild  # noqa: E402
import releases  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def zensical(root: Path, *args: str) -> int:
    env = dict(os.environ)
    here = str(Path(__file__).resolve().parent)
    env["PYTHONPATH"] = here + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    command = [sys.executable, "-m", "zensical", *args]
    print("build: " + " ".join(["zensical", *args]), flush=True)
    return subprocess.run(command, cwd=root, env=env, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the portal: every available site, then the root.")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: the checkout)")
    parser.add_argument("--release", metavar="PATH", help="build (or serve) this site only (day2/2024.1, lab)")
    parser.add_argument("--site-dir", default=releases.SITE_DIR, help="output directory, relative to the root")
    parser.add_argument("--strict", action="store_true", help="a warning of Zensical fails the build")
    parser.add_argument("--skip-vendor", action="store_true", help="do not fetch the vendored Mermaid bundle")
    parser.add_argument("--serve", action="store_true", help="live preview of one release instead of a build")
    parser.add_argument("--dev-addr", default="localhost:8000", help="address of the live preview")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    site_dir = args.site_dir.strip("/")
    try:
        registry = releases.load_registry(root)
        problems = releases.layout_problems(root, registry)
        if problems:
            raise releases.RegistryError(problems)
        if args.serve:
            selected = releases.select(registry, args.release or registry.default)
        else:
            selected = releases.select(registry, args.release)

        prebuild_args = ["--root", str(root)] + (["--skip-vendor"] if args.skip_vendor else [])
        for release in selected:
            prebuild_args += ["--release", release.path]
        if prebuild.main(prebuild_args) != 0:
            return 1

        if args.serve:
            config = releases.write_release_config(root, registry, selected[0].path, site_dir)
            return zensical(root, "serve", "-f", config.name, "--dev-addr", args.dev_addr)

        if not args.release and (root / site_dir).exists():
            shutil.rmtree(root / site_dir)
        flags = ["--clean"] + (["--strict"] if args.strict else [])
        for release in selected:
            config = releases.write_release_config(root, registry, release.path, site_dir)
            if zensical(root, "build", "-f", config.name, *flags) != 0:
                print(f"build: the build of `{release.path}` failed", file=sys.stderr)
                return 1
        config = releases.write_root(root, registry)
        if zensical(root, "build", "-f", config.name, *flags) != 0:
            print("build: the build of the root site failed", file=sys.stderr)
            return 1
        written = releases.assemble(root, registry, site_dir)
    except releases.RegistryError as error:
        for problem in error.problems:
            print(f"build: error: {problem}", file=sys.stderr)
        return 1
    built = ", ".join(release.path for release in selected)
    print(f"build: {site_dir}/ holds {built} and the root of the portal ({len(written)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
