#!/usr/bin/env python3
"""Retake the README and website screenshots from a real build (#205).

macOS only. Needs the Screen Recording and Accessibility permissions for
the terminal (window capture, key presses through System Events).

    sh scripts/macos-bundle.sh release
    python3 scripts/screenshots/shoot.py [scene ...]

Every scene starts Text³ with an empty config and recovery folder, so the
user's own settings and files are never shown or touched. The sample
files are repository files plus generated data (no personal content).
Output: docs/screenshots/<scene>.png (window only, no shadow), and the
website copy in website/screenshots/ when that folder exists.
"""

import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "target/release/Text³.app"
BIN = APP / "Contents/MacOS/text3"
OUT = ROOT / "docs/screenshots"
SIZE = (800, 600)  # points; 1600×1200 pixels on a Retina screen
PROC = "text3"


def osa(script: str) -> str:
    return subprocess.run(
        ["osascript", "-e", script], check=True, capture_output=True, text=True
    ).stdout.strip()


def front() -> None:
    osa(f'tell application "System Events" to set frontmost of process "{PROC}" to true')
    time.sleep(0.3)


def keys(text: str, using: str = "") -> None:
    """Type into Text³, which must be frontmost (checked first, so key
    presses never land in another app)."""
    front()
    if osa('tell application "System Events" to name of first process whose frontmost is true') != PROC:
        raise SystemExit("Text³ is not frontmost; not typing")
    mod = f" using {{{using}}}" if using else ""
    osa(f'tell application "System Events" to keystroke "{text}"{mod}')
    time.sleep(0.4)


def key_code(code: int) -> None:
    front()
    osa(f'tell application "System Events" to key code {code}')
    time.sleep(0.4)


def menu(top: str, item: str) -> None:
    front()
    osa(
        f'tell application "System Events" to tell process "{PROC}" to '
        f'click menu item "{item}" of menu "{top}" of menu bar 1'
    )
    time.sleep(0.6)


NOTES = """# Release checklist

Steps for a **Text³** release. Each step is small and can be checked off.

## Before tagging

1. Update `CHANGELOG.md` and move *Unreleased* under the new version.
2. Run the checks:

   ```sh
   cargo fmt --check
   cargo clippy --workspace --all-targets -- -D warnings
   cargo test --workspace --locked
   ```

3. Read the [performance budgets](docs/PERFORMANCE.md) report.

> Never tag a build that has not passed CI on all three platforms.

## Platforms

| Platform | Package          | Signed |
|----------|------------------|--------|
| macOS    | DMG, App Store   | yes    |
| Windows  | installer, zip   | soon   |
| Linux    | AppImage, deb    | n/a    |

## After publishing

- [x] Release notes written
- [ ] Website updated
- [ ] Announcement posted
"""


def samples(d: Path) -> dict:
    """Sample files: the README, the selection module, a CSV and a log."""
    files = {
        "readme": d / "README.md",
        "rust": d / "selection.rs",
        "csv": d / "inventory.csv",
        "log": d / "server.log",
    }
    shutil.copy(ROOT / "README.md", files["readme"])
    files["notes"] = d / "release-notes.md"
    files["notes"].write_text(NOTES)
    shutil.copy(ROOT / "crates/text3-core/src/selection.rs", files["rust"])
    rnd = random.Random(7)
    items = ["Notebook", "Pencil", "Stapler", "Desk lamp", "Monitor arm", "USB cable",
             "Keyboard", "Mouse pad", "Webcam", "Headset", "Marker", "Folder"]
    rows = ["sku,item,warehouse,quantity,unit_price,updated"]
    for i in range(60):
        rows.append(
            f"SKU-{1000 + i},{rnd.choice(items)},{rnd.choice(['Helsinki', 'Tampere', 'Oulu', 'Turku'])},"
            f"{rnd.randint(0, 900)},{rnd.randint(1, 300)}.{rnd.randint(0, 99):02d},2026-11-{rnd.randint(1, 27):02d}"
        )
    files["csv"].write_text("\n".join(rows) + "\n")
    lines = []
    for i in range(5000):
        lvl = rnd.choices(["INFO", "DEBUG", "WARN", "ERROR"], [60, 15, 18, 7])[0]
        svc = rnd.choice(["api", "auth", "db", "worker"])
        msg = {
            "INFO": f"request handled in {rnd.randint(40, 900)} ms",
            "DEBUG": f"cache lookup key=user:{rnd.randint(1, 999)}",
            "WARN": f"slow query took {rnd.randint(100, 600)} ms",
            "ERROR": f"upstream timeout after {rnd.randint(50, 900)} ms",
        }[lvl]
        h, m, s = divmod(i, 3600)[0], divmod(i, 60)[0] % 60, i % 60
        lines.append(f"2026-11-28T{9 + h:02d}:{m:02d}:{s:02d}Z {lvl:<5} {svc:<6} {msg}")
    files["log"].write_text("\n".join(lines) + "\n")
    return files


def caret_at(path: Path, line: int, col: int) -> int:
    text = path.read_text()
    starts = [0]
    for ln in text.split("\n"):
        starts.append(starts[-1] + len(ln) + 1)
    return starts[line - 1] + col - 1


def session(tabs, active: int, extra: str = "") -> str:
    out = f"text3-session 1\nactive={active}\n"
    for path, caret in tabs:
        out += f"path={path}\n"
        if caret is not None:
            out += f"caret={caret},{caret}\n"
    return out + extra


def run(name: str, files: dict, theme: str, sess: str, args=(), act=None) -> None:
    with tempfile.TemporaryDirectory(prefix="text3-shot-") as tmp:
        tmp = Path(tmp)
        cfg, rec = tmp / "config", tmp / "state/recovery"
        cfg.mkdir()
        rec.mkdir(parents=True)
        (cfg / "settings").write_text(
            "text3-settings 1\nfont_size=12\ntab_width=4\ninsert_spaces=true\n"
            f"theme={theme}\nrestore_session=true\ncheck_updates=false\n"
            "last_update_check=0\nlocal_history=false\nword_wrap=false\nhot_exit=false\n"
            "show_counts=false\ndefault_apps_asked=true\n"
        )
        if sess:
            (tmp / "state/session").write_text(sess)
        env = dict(os.environ, TEXT3_CONFIG_DIR=str(cfg), TEXT3_RECOVERY_DIR=str(rec))
        p = subprocess.Popen([str(BIN), *map(str, args)], env=env,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(2.5)
            front()
            osa(
                f'tell application "System Events" to tell process "{PROC}" to tell window 1\n'
                f"set position to {{120, 80}}\nset size to {{{SIZE[0]}, {SIZE[1]}}}\nend tell"
            )
            time.sleep(0.8)
            if act:
                act()
            time.sleep(1.0)
            wid = subprocess.run([str(WINID), str(p.pid)], check=True, capture_output=True,
                                 text=True).stdout.strip()
            out = OUT / f"{name}.png"
            subprocess.run(["screencapture", "-x", "-o", "-l", wid, str(out)], check=True)
            print(f"{name}: {out.relative_to(ROOT)}")
        finally:
            p.terminate()
            p.wait(timeout=10)


def main() -> None:
    if not BIN.exists():
        raise SystemExit("build first: sh scripts/macos-bundle.sh release")
    work = Path(tempfile.mkdtemp(prefix="text3-samples-"))
    f = samples(work)
    rs222 = caret_at(f["rust"], 222, 24)
    three = [(f["readme"], None), (f["csv"], None), (f["rust"], rs222)]

    def find():
        keys("f", "command down")
        keys("selection")

    def log():
        menu("File", "Open in Log Viewer…")
        time.sleep(1.0)
        keys("g", "command down, shift down")
        keys(str(f["log"]))
        key_code(36)  # Return: go to the file
        time.sleep(0.8)
        key_code(36)  # Return: open
        time.sleep(1.5)

    scenes = {
        "editor": dict(theme="dark", sess=session(three, 2)),
        "find": dict(theme="dark", sess=session([(f["readme"], None), (f["csv"], None), (f["rust"], 0)], 2), act=find),
        "markdown": dict(theme="dark", sess=session([(f["notes"], 0)], 0),
                         act=lambda: menu("View", "Markdown Source and Preview")),
        "csv": dict(theme="dark", sess=session([(f["csv"], 0)], 0),
                    act=lambda: menu("View", "Structured View (CSV, JSON, XML, YAML)")),
        "light": dict(theme="light", sess=session([(f["rust"], caret_at(f["rust"], 186, 1))], 0)),
        "split": dict(theme="dark", sess=session(
            [(f["rust"], caret_at(f["rust"], 186, 1)), (f["readme"], 0)], 0,
            "split=right\ngroup=0.5\npane=0,1\ngroup=0.5\npane=1,1\nfocus=0\n"), act=front),
        "log": dict(theme="dark", sess="", act=log),
    }
    want = sys.argv[1:] or list(scenes)
    for name in want:
        s = scenes[name]
        run(name, f, s["theme"], s["sess"], act=s.get("act"))
    site = ROOT / "website/screenshots"
    if site.is_dir():
        for name in want:
            shutil.copy(OUT / f"{name}.png", site / f"{name}.png")
    shutil.rmtree(work)


WINID = Path(os.environ.get("TEXT3_WINID", Path(tempfile.gettempdir()) / "text3-winid"))
if __name__ == "__main__":
    if not WINID.exists():
        subprocess.run(["swiftc", "-O", str(Path(__file__).with_name("winid.swift")), "-o", str(WINID)],
                       check=True)
    main()
