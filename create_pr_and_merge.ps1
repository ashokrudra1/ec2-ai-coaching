Param(
    [string]$RepoPath = "C:\Users\HP\Documents\GitHub\ec2-ai-coaching.worktrees\agents-ai-coach-improvement-suggestions"
)

Set-StrictMode -Version Latest

function Abort([string]$msg){ Write-Host "ERROR: $msg" -ForegroundColor Red; exit 1 }

Write-Host "Repository path: $RepoPath"
if (-not (Test-Path $RepoPath)) { Abort "Repo path not found. Update the script param or run from repo root." }

Push-Location $RepoPath

# Prereqs
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Abort "git not found in PATH. Install Git for Windows." }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Abort "gh CLI not found in PATH. Install GitHub CLI: https://cli.github.com/" }

if (-not $env:GITHUB_TOKEN) {
    Abort "GITHUB_TOKEN environment variable not set. Set it before running: `$env:GITHUB_TOKEN='YOUR_PAT'` (PowerShell session)"
}

# Fetch and checkout
Write-Host "Fetching origin..."
git fetch origin --quiet || Abort "git fetch failed"

$branch = 'agents-ai-coach-improvement-suggestions'
$exists = (git ls-remote --heads origin $branch) -ne $null
if ($exists) {
    Write-Host "Checking out remote branch $branch"
    git checkout $branch -q || git checkout -b $branch
    git pull origin $branch --ff-only || Write-Host "Warning: fast-forward pull failed; manual intervention may be required."
} else {
    Write-Host "Local branch $branch will be created from current HEAD"
    git checkout -b $branch || Abort "Failed to create branch $branch"
}

# Ensure clean or stash
$status = git status --porcelain
if ($status) {
    Write-Host "Working tree is dirty. Creating commit on temporary branch to preserve changes."
    $timestamp = (Get-Date -Format "yyyyMMddHHmmss")
    $tempBranch = "local-changes-$timestamp"
    git checkout -b $tempBranch || Abort "Failed to create temp branch"
    git add -A
    git commit -m "chore: preserve local changes $timestamp" || Write-Host "No changes to commit"
    git checkout $branch
    git merge --no-ff $tempBranch -m "merge: include local changes before PR" || Write-Host "Merge may have conflicts; please resolve manually"
}

# Push branch
Write-Host "Pushing branch to origin..."
git push origin $branch --set-upstream || Abort "git push failed"

# Authenticate gh using token from env
Write-Host "Authenticating gh CLI using GITHUB_TOKEN..."
$env:GITHUB_TOKEN | gh auth login --with-token 2>$null || Write-Host "gh auth login may have failed; ensure GITHUB_TOKEN has correct scopes (repo, workflow)."

# Create PR
$prTitle = "Complete 10-Phase AI Coach — full implementation (Phases 1–10)"
$prBody = @'
Implements full end-to-end AI Coach: daily Strava syncs, IntelligentCoach (GPT-4), memory pipeline, proactive scheduler, multi-sport metrics, dashboard, tests, Docker/K8s and CI.
See COMPLETE_IMPLEMENTATION_SUMMARY.md and FINAL_SUMMARY.txt for full details, test plan, and deployment steps.
'@

Write-Host "Creating Pull Request..."
$createArgs = @(
    'pr','create',
    '--base','main',
    '--head',$branch,
    '--title',$prTitle,
    '--body',$prBody
)

gh @createArgs || Abort "gh pr create failed. You may need additional permissions or manual PR creation."

# Open PR in browser
Write-Host "Opening PR in browser..."
gh pr view --web || Write-Host "PR created. Use 'gh pr list' to view."

Pop-Location
Write-Host "Done. If errors occurred, inspect output above."
