# CallLens Rollback & Disaster Recovery Procedures

This guide provides operational steps to safely reset or roll back CallLens Stress Lab state without data loss or repository corruption.

---

## 1. Rolling Back Database State

If a benchmark run terminates prematurely or data needs re-evaluation:

- **Targeted Experiment Rollback:**
  Connect to SQLite (`sqlite3 ../calllens-data/benchmark.db` or via Python):
  ```sql
  -- Roll back a specific experiment (e.g. Experiment F)
  DELETE FROM benchmark_results WHERE experiment = 'F';
  ```
- **Complete Benchmark Reset:**
  Delete the database file:
  ```powershell
  Remove-Item "../calllens-data/benchmark.db" -ErrorAction SilentlyContinue
  ```
  Running `python calllens/benchmark.py` will recreate an empty database schema automatically.

---

## 2. Cache Invalidation & Rollback

CallLens caches successful responses by SHA-256 hash in `../calllens-data/cache/`:

- **Purge Specific Cache Key:**
  Delete the corresponding JSON file:
  ```powershell
  Remove-Item "../calllens-data/cache/<sha256_key>.json"
  ```
- **Flush Entire Cache:**
  ```powershell
  Remove-Item -Recurse -Force "../calllens-data/cache/*"
  ```

---

## 3. Environment & Virtualenv Restoration

If Python dependencies become corrupted or misconfigured:

1. Deactivate current environment.
2. Remove `.venv`:
   ```powershell
   Remove-Item -Recurse -Force .venv
   ```
3. Re-create and restore pinned dependencies:
   ```powershell
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
   ```
4. Verify tests pass:
   ```powershell
   .venv\Scripts\pytest -q
   ```

---

## 4. Git Working Tree Reset

To revert uncommitted code modifications while preserving external datasets:
```powershell
git status --short
git restore .
git clean -fd
```
*(Datasets in `../calllens-data` reside outside the git tree and will remain completely unaffected).*
