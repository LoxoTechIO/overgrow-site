#!/usr/bin/env python3
"""Build static theme gallery data for overgrow-site.

Reads the OverGrow-Theme repo (a local clone if available, otherwise a
shallow clone from GitHub), copies each .overgrowpack and its preview
image into the site's assets, and emits themes.json for themes.html.

Usage:
  python3 Scripts/build_themes.py [--repo /path/to/OverGrow-Theme]

Outputs (relative to repo root of overgrow-site):
  assets/themes/<slug>.overgrowpack
  assets/themes/previews/<slug>.png
  themes.json
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

THEME_REPO_URL = "https://github.com/LoxoTechIO/OverGrow-Theme"
SITE_ROOT = Path(__file__).resolve().parent.parent


def slug_en(slug: str) -> str:
    return " ".join(w.capitalize() for w in slug.split("-"))


def load_pack(pack_path: Path) -> dict:
    with zipfile.ZipFile(pack_path) as z:
        return json.loads(z.read("theme.json").decode("utf-8"))


def collect(repo_dir: Path) -> list:
    themes_dir = repo_dir / "themes"
    previews_dir = themes_dir / "previews"
    out = []
    for pack in sorted(themes_dir.glob("*.overgrowpack")):
        slug = pack.stem
        try:
            meta = load_pack(pack)
        except Exception as e:
            print(f"  ! skip {pack.name}: cannot read theme.json ({e})", file=sys.stderr)
            continue
        preview = previews_dir / f"{slug}.png"
        out.append({
            "slug": slug,
            "name": meta.get("name") or slug,
            "en": slug_en(slug),
            "subtitle": meta.get("subtitle", ""),
            "author": meta.get("author", ""),
            "version": meta.get("version", ""),
            "accent": (meta.get("tokens") or {}).get("accent")
                      or (meta.get("palette") or {}).get("accent") or "4a7c3f",
            "file": f"assets/themes/{pack.name}",
            "preview": f"assets/themes/previews/{slug}.png" if preview.exists() else None,
            "size": pack.stat().st_size,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", help="path to a local OverGrow-Theme clone")
    args = ap.parse_args()

    tmp = None
    if args.repo:
        repo_dir = Path(args.repo).expanduser().resolve()
        if not (repo_dir / "themes").is_dir():
            print(f"error: no themes/ directory in {repo_dir}", file=sys.stderr)
            return 1
    else:
        sibling = SITE_ROOT.parent / "OverGrow-Theme"
        if (sibling / "themes").is_dir():
            repo_dir = sibling
            print(f"using local clone: {repo_dir}")
        else:
            tmp = tempfile.mkdtemp(prefix="og-themes-")
            repo_dir = Path(tmp) / "OverGrow-Theme"
            print(f"cloning {THEME_REPO_URL} ...")
            subprocess.run(["git", "clone", "--depth", "1", THEME_REPO_URL, str(repo_dir)],
                           check=True)

    themes = collect(repo_dir)
    if not themes:
        print("error: no usable packs found", file=sys.stderr)
        return 1

    assets = SITE_ROOT / "assets" / "themes"
    (assets / "previews").mkdir(parents=True, exist_ok=True)

    # Remove stale packs/previews so deleted themes don't linger.
    for old in assets.glob("*.overgrowpack"):
        old.unlink()
    for old in (assets / "previews").glob("*.png"):
        old.unlink()

    for t in themes:
        shutil.copy2(repo_dir / "themes" / f"{t['slug']}.overgrowpack",
                     SITE_ROOT / t["file"])
        if t["preview"]:
            shutil.copy2(repo_dir / "themes" / "previews" / f"{t['slug']}.png",
                         SITE_ROOT / t["preview"])

    data = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "themes": themes,
    }
    out_json = SITE_ROOT / "themes.json"
    out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(f"built {len(themes)} themes -> {out_json}")
    if tmp:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
