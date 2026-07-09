<h1 align="center">🎬 Chrome Multi-Profile Playlist Automation</h1>

<p align="center">
  <b>Launch dozens of your existing Google Chrome profiles, open playlist tabs in each, tile them into a grid, and start playback — all from one command.</b>
</p>

<p align="center">
  <a href="#"><img src="https://img.shields.io/badge/status-production--ready-brightgreen?style=for-the-badge" alt="Status" /></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-32%20passing-success?style=for-the-badge&logo=pytest&logoColor=white" alt="Tests" /></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" /></a>
  <a href="#"><img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Platform" /></a>
  <a href="#"><img src="https://img.shields.io/badge/license-MIT-blue?style=for-the-badge" alt="License" /></a>
</p>

<p align="center">
  <b>Built with</b><br/><br/>
  <img src="https://skillicons.dev/icons?i=python,vscode,git,github&theme=dark" alt="Python, VS Code, Git, GitHub" />
  <br/>
  <img src="https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge&logo=playwright&logoColor=white" alt="Playwright" />
  <img src="https://img.shields.io/badge/Google%20Chrome-4285F4?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Google Chrome" />
  <img src="https://img.shields.io/badge/YAML-CB171E?style=for-the-badge&logo=yaml&logoColor=white" alt="YAML" />
  <img src="https://img.shields.io/badge/loguru-000000?style=for-the-badge&logo=python&logoColor=white" alt="loguru" />
  <img src="https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white" alt="pytest" />
</p>

<p align="center">
  <sub>Crafted with ❤️ by <b>Techie Krishna Kayaking</b> · <a href="#-author--connect-with-me">Connect with me ↓</a></sub>
</p>

---

A production-grade, modular CLI framework that launches your **existing** Google
Chrome profiles, opens multiple playlist URLs (YouTube, Spotify, YouTube Music,
or anything else) as tabs in each profile, arranges the windows into a grid, and
starts playback automatically.

> **Windows-first**, with a cross-platform abstraction so it also runs on macOS
> and Linux for launching and tab-opening (window arrangement is Windows-only
> today and degrades gracefully elsewhere).

- **No Selenium.** Native Chrome command-line launching by default.
- **No temporary profiles.** Reuses your already-logged-in profiles. Cookies and
  sessions are never touched.
- **Optional Playwright** playback control over the Chrome DevTools Protocol
  (only when you enable it).

---

## Table of contents

1. [How it works](#how-it-works)
2. [Requirements](#requirements)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running](#running)
6. [Profile detection](#profile-detection)
7. [Window arrangement](#window-arrangement)
8. [Playback automation](#playback-automation)
9. [Logging & reports](#logging--reports)
10. [Project structure](#project-structure)
11. [Testing](#testing)
12. [Troubleshooting](#troubleshooting)
13. [Common Chrome issues](#common-chrome-issues)
14. [Author & connect with me](#-author--connect-with-me)

---

## How it works

For every selected profile the framework:

1. Builds a Chrome command line targeting the real `User Data` directory and the
   profile's `--profile-directory` (e.g. `"Profile 3"`).
2. Launches Chrome as a **new window** with all playlist URLs as tabs.
3. Moves/resizes the window into its grid cell (Windows).
4. Optionally connects Playwright over remote debugging to force playback.
5. Waits `delay_between_profiles` seconds and moves to the next profile.

```
+-----+-----+-----+
| P1  | P2  | P3  |
+-----+-----+-----+
| P4  | P5  | P6  |
+-----+-----+-----+
```

---

## Requirements

- **Windows 11** (primary target). macOS/Linux supported for launch + tabs.
- **Python 3.12+**
- **Google Chrome** installed normally and already logged into your accounts.

---

## Installation

```powershell
# From the project folder (tkk-YT_PlaylistChrome)
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # Windows PowerShell
# source .venv/bin/activate           # macOS/Linux

pip install -r requirements.txt

# Only needed if you set playback.mode: playwright
playwright install chromium
```

The Windows-only window-management packages (`pygetwindow`, `pywinauto`,
`pywin32`) are declared with platform markers, so `pip install -r requirements.txt`
works on macOS/Linux too — they simply aren't installed there.

---

## Configuration

Configuration lives in [`config/config.yaml`](config/config.yaml). Every key has
a safe default, so a minimal config just needs playlists:

```yaml
playlists:
  - https://www.youtube.com/playlist?list=XXXX
  - https://open.spotify.com/playlist/YYYY

profiles:            # empty = launch ALL discovered profiles
  - Default
  - Profile 1
  - Profile 3

delay_between_profiles: 8
delay_between_tabs: 2

window:
  width: 650
  height: 500

grid:
  columns: 3

playback:
  autoplay: true
  mode: native        # native | playwright
```

Key options:

| Key | Meaning |
| --- | --- |
| `chrome_path` | Chrome executable. Blank = auto-detect. |
| `user_data_dir` | Chrome `User Data` folder. Blank = auto-detect. |
| `profiles` | Profile **directory** names to launch. Empty = all. |
| `exclude_profiles` | Always-skipped profile directories. |
| `playlists` | Any http/https URLs. One tab per URL. |
| `delay_between_profiles` | Seconds between profile launches. |
| `delay_between_tabs` | Seconds between tabs / readiness pauses. |
| `window.width/height` | Per-window size in pixels. |
| `grid.columns` | Windows per row. |
| `playback.autoplay` | Attempt to start playback. |
| `playback.mode` | `native` (URL autoplay) or `playwright` (force play). |
| `execution.parallel` | Launch profiles concurrently. |
| `execution.max_concurrent` | Max simultaneous windows when parallel. |
| `execution.retries` | Retry attempts per profile. |

---

## Running

```powershell
# Use the default config/config.yaml
python3 main.py

# Explicit config file
python3 main.py --config config/config.yaml

# Only specific profiles (overrides config)
python3 main.py --profiles "Profile 1,Profile 3"

# See exactly what would happen, without launching anything
python3 main.py --dry-run

# List the Chrome profiles the tool can see, then exit
python3 main.py --list-profiles

# Override log verbosity
python3 main.py --log-level DEBUG
```

Exit codes: `0` success, `1` nothing to do, `2` config error, `3` setup error,
`4` one or more profiles failed, `130` interrupted (Ctrl+C).

---

## Profile detection

Profiles are discovered automatically from the Chrome `User Data` directory:

- **Windows:** `%LOCALAPPDATA%\Google\Chrome\User Data`
- **macOS:** `~/Library/Application Support/Google/Chrome`
- **Linux:** `~/.config/google-chrome`

Directories matching `Default` or `Profile N` are treated as profiles. Friendly
account names are read from each profile's `Preferences` file when available, so
`--list-profiles` shows both the directory and the account name.

Use `profiles` to include, and `exclude_profiles` to skip (e.g. `System Profile`,
`Guest Profile`).

---

## Window arrangement

Initial size/position is set via Chrome's `--window-size` and
`--window-position` flags on every platform. On **Windows**, `pygetwindow` then
moves/resizes each window precisely into its grid cell. Configure the grid with
`grid.columns`, `grid.padding`, and `grid.origin_x/y`. Extra profiles wrap onto
new rows automatically.

On macOS/Linux, window arrangement is skipped (logged at DEBUG) and Chrome's own
positioning flags are used.

---

## Playback automation

Two modes:

- **`native`** (default): opens the tabs and relies on the site's own autoplay.
  For YouTube URLs an `autoplay=1` hint is appended automatically.
- **`playwright`**: Chrome is launched with `--remote-debugging-port` (base port
  `playback.remote_debugging_port`, incremented per profile). Playwright connects
  over CDP **to the already-running browser** and, per tab:
  1. skips tabs already playing,
  2. clicks a known play-button selector (`playback.play_selectors`),
  3. falls back to pressing the **Space** key.

  Playwright never opens a new browser or profile and never clears cookies. It
  detaches when done. No screen coordinates are used.

To use it:

```yaml
playback:
  autoplay: true
  mode: playwright
  remote_debugging_port: 9222
```

…and run `playwright install chromium` once.

---

## Logging & reports

Structured logs (via `loguru`) are written to `logs/`:

- `logs/automation.log` — all events (timestamp, profile, level, message).
- `logs/errors.log` — warnings and errors only.

Logs rotate at `logging.rotation` and are retained for `logging.retention`.

A machine-readable **JSON execution report** is written to
`logs/execution_report.json` (configurable), including per-profile success,
attempts, tabs opened, tabs playing, PID, elapsed time and any error. A
human-readable summary is also printed at the end of each run.

---

## Project structure

```
tkk-YT_PlaylistChrome/
├── config/
│   └── config.yaml
├── automation/
│   ├── __init__.py
│   ├── config.py            # typed config dataclasses + YAML loader
│   ├── logging_utils.py     # loguru setup
│   ├── utils.py             # retry decorator, stopwatch, platform helpers
│   ├── profile_manager.py   # profile discovery / selection
│   ├── chrome.py            # Chrome/user-data detection + launcher
│   ├── window_manager.py    # grid computation + window arrangement
│   ├── playlist.py          # URL parsing / provider detection
│   ├── playback.py          # Playwright CDP playback controller
│   ├── report.py            # JSON report + summary
│   └── launcher.py          # orchestration (sequential/parallel, retries)
├── tests/                   # unit + integration tests (pytest)
├── logs/
├── main.py                  # CLI entry point
├── requirements.txt
├── pytest.ini
└── README.md
```

---

## Testing

```powershell
pip install -r requirements.txt
pytest
```

The suite covers config parsing/validation, profile discovery/selection, Chrome
command building, the retry decorator, playlist parsing, grid math, and an
end-to-end launcher **dry-run** integration test (no real Chrome required).

---

## Troubleshooting

**"Could not locate the Chrome executable."**
Set `chrome_path` in `config.yaml` to your `chrome.exe` full path.

**"Could not locate the Chrome 'User Data' directory."**
Set `user_data_dir` explicitly. Find it by opening `chrome://version` and
reading the "Profile Path" (the parent folder is `User Data`).

**A requested profile is skipped.**
Run `python main.py --list-profiles` to see valid **directory** names — use
`Profile 1`, not the friendly account name.

**Playback doesn't start in `native` mode.**
Many sites block autoplay with sound. Switch to `playback.mode: playwright`.

**Playwright errors / not installed.**
Run `pip install playwright` then `playwright install chromium`, or set
`playback.mode: native`.

---

## Common Chrome issues

- **Only ONE profile window opens (macOS):** This is a Chrome platform
  limitation, not a framework bug. Chrome runs a **single browser process per
  `User Data` directory**. When Chrome is already running, each new
  `chrome --profile-directory=...` launch is *forwarded* to that one process. On
  **Windows 11 (the primary target)** the running process reliably opens a
  **separate window per profile**, so all profiles appear. On **macOS** the
  forwarded request is often collapsed into the existing window, so extra
  profile windows may not open. Workarounds on macOS:
  - Run on Windows for the full multi-profile grid (intended platform), or
  - Quit Chrome completely first, then run the tool so it owns the process, or
  - Launch fewer profiles / one at a time.
- **Windows appeared but most were off-screen:** fixed by `grid.auto_fit: true`
  (default), which tiles every launched window to fit your detected screen. With
  `auto_fit: false` and many profiles, rows can extend below the screen — either
  re-enable auto-fit or lower `window.width/height`.
- **Chrome already running:** the tool passes `--new-window`, so a new window
  opens under the existing Chrome process. Profiles/sessions are preserved.
- **`--remote-debugging-port` ignored:** this flag only takes effect when Chrome
  starts fresh for that user-data dir. If a Chrome instance is already running
  for the same profile without the port, close all Chrome windows first, or use
  `native` mode.
- **Multiple windows land on top of each other:** keep `grid.auto_fit: true`, or
  increase `grid.padding` / reduce `window.width/height` in fixed mode.
- **Windows not being arranged:** ensure you're on Windows with `pygetwindow`
  installed; on macOS/Linux only Chrome's own positioning applies.

---

## 👨‍💻 Author & connect with me

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Source+Code+Pro&weight=700&size=28&duration=2600&pause=1000&color=33C3FF&center=true&vCenter=true&width=800&height=60&lines=Built+by+Techie+Krishna+Kayaking;Senior+Data+Engineer+%E2%80%A2+AI-First+Builder" alt="Techie Krishna Kayaking" />
</p>

<p align="center">
  <b>Krishna Kayaking</b><br/>
  Senior Data Engineer • Data Testing &amp; Automation Leader • AI-First Builder<br/>
  <sub>9+ years building enterprise Data Platforms, Big Data Pipelines &amp; automation frameworks across AWS, Azure &amp; GCP.</sub>
</p>

<p align="center">
  <a href="https://www.linkedin.com/in/krishnakayaking/"><img src="https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white" alt="LinkedIn" /></a>&nbsp;
  <a href="https://www.youtube.com/@TechieKrishnaKayaking"><img src="https://img.shields.io/badge/YouTube-FF0000?style=for-the-badge&logo=youtube&logoColor=white" alt="YouTube" /></a>&nbsp;
  <a href="https://www.techiekrishnakayaking.com/"><img src="https://img.shields.io/badge/Website-000000?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Website" /></a>&nbsp;
  <a href="https://topmate.io/techie_krishna_kayaking"><img src="https://img.shields.io/badge/Topmate-FFCA28?style=for-the-badge&logo=bookstack&logoColor=black" alt="Topmate" /></a>&nbsp;
  <a href="https://www.instagram.com/techiekrishnakayaking/"><img src="https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white" alt="Instagram" /></a>
</p>

<p align="center">
  <sub>💡 If this project helped you, consider giving it a ⭐ and subscribing on <a href="https://www.youtube.com/@TechieKrishnaKayaking">YouTube</a>.</sub>
</p>

<p align="center">
  <sub>© 2026 Techie Krishna Kayaking · Released under the MIT License · Made with ❤️ and Python</sub>
</p>
