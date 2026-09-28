# GitHub Setup Instructions

## Step 1: Create Repository on GitHub
1. Go to https://github.com/ashwin-v-s
2. Click "New" repository
3. Name: `data-lineage-engine`
4. Make it **Private**
5. **Do NOT** add README, .gitignore, or license
6. Click "Create repository"

## Step 2: Push Code to GitHub
Run these commands in the project directory:

```bash
cd d:\Meta_Data\data-lineage-engine
git remote add origin https://github.com/ashwin-v-s/data-lineage-engine.git
git push -u origin main
```

## Step 3: Add Team Members as Collaborators
1. Go to your repository: https://github.com/ashwin-v-s/data-lineage-engine
2. Click **Settings** (top menu)
3. Click **Collaborators** (left sidebar)
4. Click **Add people** (green button)
5. Enter each team member's GitHub username or email
6. Select their role (usually "Write" or "Maintain")
7. Click **Add [username] to this repository**

Each member will receive an email invitation to join.

## Step 4: Protect Main Branch (IMPORTANT!)
1. Go to **Settings** > **Branches**
2. Click **Add branch protection rule**
3. Branch name pattern: `main`
4. Enable these settings:
   - ✅ **Require a pull request before merging**
   - ✅ **Require approvals** (at least 1)
   - ✅ **Require review from Code Owners**
   - ✅ **Require status checks to pass before merging**
   - ✅ **Require branches to be up to date before merging**
   - In "Status checks": add `test` (after first CI run)
   - ✅ **Do not allow bypassing the above settings**
5. Click **Create**

## Step 5: Update CODEOWNERS
Edit `.github/CODEOWNERS` and replace placeholder handles with actual GitHub usernames:

```
# Replace @M1-handle with actual usernames
/ingestion/sql/        @actual-username-m1
/ingestion/dbt/        @actual-username-m1
# ... and so on
```

## Team Member Setup (Everyone)
Each team member should:

```bash
git clone https://github.com/ashwin-v-s/data-lineage-engine.git
cd data-lineage-engine
python -m venv .venv
.venv\Scripts\activate              # Windows
pip install pytest
python scripts/check_import_boundaries.py
python -m pytest -q
```

## Create Feature Branches
Each member creates their branch:

```bash
git switch -c feature/static-lineage        # M1
git switch -c feature/runtime-groundtruth   # M2
git switch -c feature/bitemporal-storage    # M3
git switch -c feature/reasoning-experiments # M4
git switch -c feature/backend-ui            # M5
```

## Workflow for All Members
1. Work on your feature branch
2. **Never push to main directly**
3. Open Pull Request when ready
4. Get code owner approval
5. Wait for CI to pass (green check)
6. Merge to main
