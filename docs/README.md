# τ² Bench – Trajectory Viewer (GitHub Pages)

This folder is a **static site** for viewing simulation trajectories. It is intended to be published as a **GitHub Page**.

## Local preview

1. **Generate trajectory data** (from repo root or `tau2-bench`):

   ```bash
   cd tau2-bench
   python3 scripts/export_trajectories_for_pages.py
   ```

   This writes `docs/data/index.json` and `docs/data/task_<id>.json` for each simulated task.

2. **Serve the docs folder** (any static server):

   ```bash
   cd tau2-bench/docs
   python3 -m http.server 8080
   ```

   Then open **http://localhost:8080** (or **http://localhost:8080/index.html**).

   Alternatively, open `index.html` directly in a browser. If you see “Could not load task index”, run the script above from `tau2-bench` so that `data/index.json` exists.

## GitHub Pages setup

1. In the GitHub repo: **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
3. Choose branch **main** (or your default), folder **/docs**, then **Save**.
4. Ensure trajectory data is committed: run `export_trajectories_for_pages.py` and commit the `docs/data/` output (or add a CI step to generate it before deploy).

The site will be available at:

- **User/org site:** `https://<username>.github.io/<repo>/`  
  If the root is not the repo name, add in `index.html` and `viewer.html` inside `<head>`:
  ```html
  <base href="/YOUR_REPO_NAME/" />
  ```
  and ensure the export script and JS use this base for fetching `data/*.json`.

- **Project site:** `https://<username>.github.io/<repo>/` (same; `/docs` as source uses repo name as base path).

## What’s included

- **index.html** – List of all tasks with reward (pass/fail), duration, scenario preview, and link to the trajectory viewer.
- **viewer.html** – For a single task: task details, run info, evaluation (reward, DB, action checks, communicate checks), and full conversation with tool calls and results.
- **js/index.js** – Loads `data/index.json`, renders the table, filter (all / passed / failed).
- **js/viewer.js** – Reads `?task=<id>`, loads `data/task_<id>.json`, renders task, run, evaluation, and messages.
- **css/style.css** – Styles for index and viewer (dark theme, timeline, badges).

All links and script fetches use relative paths so the site works when opened from the filesystem or when served from a subpath (e.g. `/<repo>/`).
