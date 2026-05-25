Param(
    [string]$RepoPath = "C:\Users\HP\Documents\GitHub\ec2-ai-coaching.worktrees\agents-ai-coach-improvement-suggestions"
)

Set-StrictMode -Version Latest

function Abort([string]$msg){ 
    Write-Host "ERROR: $msg" -ForegroundColor Red
    Pop-Location
    exit 1 
}

Write-Host "Repository path: $RepoPath"
if (-not (Test-Path $RepoPath)) { Abort "Repo path not found. Update the script param or run from repo root." }

Push-Location $RepoPath

# Prereqs
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Abort "git not found in PATH. Install Git for Windows." }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Abort "gh CLI not found in PATH. Install GitHub CLI: https://cli.github.com/" }

if (-not $env:GITHUB_TOKEN) {
    Abort "GITHUB_TOKEN environment variable not set. Set it before running: `$env:GITHUB_TOKEN='YOUR_PAT'`"
}

# Fetch
Write-Host "Fetching origin..."
git fetch origin --quiet
if ($LASTEXITCODE -ne 0) { Abort "git fetch failed" }

$branch = 'agents-ai-coach-improvement-suggestions'
$ls = git ls-remote --heads origin $branch 2>$null
$exists = -not [string]::IsNullOrEmpty($ls)

if ($exists) {
    Write-Host "Checking out remote branch $branch"
    git checkout $branch
    if ($LASTEXITCODE -ne 0) { 
        Write-Host "Local checkout failed, creating local branch from origin/$branch"
        git checkout -b $branch origin/$branch
        if ($LASTEXITCODE -ne 0) { Abort "Failed to create branch $branch from origin/$branch" } 
    }
    git pull origin $branch --ff-only
    if ($LASTEXITCODE -ne 0) { Write-Host "Warning: fast-forward pull failed; manual intervention may be required." }
} else {
    Write-Host "Creating local branch $branch from current HEAD"
    git checkout -b $branch
    if ($LASTEXITCODE -ne 0) { Abort "Failed to create branch $branch" }
}

# Preserve local changes if any
$status = git status --porcelain
if (-not [string]::IsNullOrEmpty($status)) {
    Write-Host "Working tree is dirty. Committing local changes to temporary branch to preserve them."
    $timestamp = (Get-Date -Format "yyyyMMddHHmmss")
    $tempBranch = "local-changes-$timestamp"
    git checkout -b $tempBranch
    if ($LASTEXITCODE -ne 0) { Abort "Failed to create temp branch" }
    
    git add -A
    git commit -m "chore: preserve local changes $timestamp"
    if ($LASTEXITCODE -ne 0) { Write-Host "No changes to commit or commit failed" }
    
    git checkout $branch
    git merge --no-ff $tempBranch -m "merge: include local changes before PR"
    if ($LASTEXITCODE -ne 0) { Write-Host "Merge may have conflicts; please resolve manually" }
}

# Push branch
Write-Host "Pushing branch to origin..."
git push origin $branch --set-upstream
if ($LASTEXITCODE -ne 0) { Abort "git push failed" }

# Authenticate gh using token
Write-Host "Authenticating gh CLI using GITHUB_TOKEN..."
$token = $env:GITHUB_TOKEN
if (-not $token) { 
    Write-Host "GITHUB_TOKEN not found; skipping gh auth." 
} else {
    $token | gh auth login --with-token
    if ($LASTEXITCODE -ne 0) { Write-Host "gh auth login may have failed; ensure GITHUB_TOKEN has repo and workflow scopes." }
}

# Create PR
$prTitle = 'Complete 10-Phase AI Coach - full implementation (Phases 1-10)'

# Flattened single-line string with explicit PowerShell line breaks (`n) to avoid here-string bugs
$prBody = "Implements full end-to-end AI Coach: daily Strava syncs, IntelligentCoach (GPT-4), memory pipeline, proactive scheduler, multi-sport metrics, dashboard, tests, Docker/K8s and CI.`nSee COMPLETE_IMPLEMENTATION_SUMMARY.md and FINAL_SUMMARY.txt for full details, test plan, and deployment steps."

Write-Host "Creating Pull Request..."
gh pr create --base main --head $branch --title "$prTitle" --body "$prBody"
if ($LASTEXITCODE -ne 0) { Abort "gh pr create failed. You may need additional permissions or manual PR creation." }

# Open PR in browser
Write-Host "Opening PR in browser..."
gh pr view --web
if ($LASTEXITCODE -ne 0) { Write-Host "PR created. Use 'gh pr list' to view." }

Pop-Location
Write-Host "Done. If errors occurred, inspect output above."