$ErrorActionPreference = "Stop"

Write-Host "`n=== CivicQuest Cloud Run Deployment ===" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Deploy from source ────────────────────────────────────────────────
# NOTE: Do NOT pass PORT as an env var — Cloud Run sets it automatically.
# Only pass app-specific secrets/config.

Write-Host "[1/3] Building and deploying to Cloud Run..." -ForegroundColor Yellow

gcloud run deploy civicquest `
    --source . `
    --region asia-south1 `
    --project starry-runner-482513-c5 `
    --port 8080 `
    --allow-unauthenticated `
    --set-env-vars "GEMINI_API_KEY=AIzaSyAPBSwIM_R3ew_lABlkp5_GYYxEja9AXAE,GOOGLE_MAPS_API_KEY=AIzaSyA76Zp3-IUCe3hiHwYYrxqiXp9WY67OE28,FLASK_SECRET_KEY=civicquest2026secret,GOOGLE_CLOUD_PROJECT=starry-runner-482513-c5"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Deployment failed! See error above." -ForegroundColor Red
    exit 1
}

Write-Host "[1/3] Deploy succeeded!" -ForegroundColor Green

# ── Step 2: Grant unauthenticated access via IAM ──────────────────────────────
Write-Host "[2/3] Setting IAM policy for unauthenticated access..." -ForegroundColor Yellow

gcloud run services add-iam-policy-binding civicquest `
    --region asia-south1 `
    --project starry-runner-482513-c5 `
    --member="allUsers" `
    --role="roles/run.invoker" `
    --quiet

Write-Host "[2/3] IAM policy set!" -ForegroundColor Green

# ── Step 3: Show service URL ──────────────────────────────────────────────────
Write-Host "[3/3] Fetching service URL..." -ForegroundColor Yellow

gcloud run services describe civicquest `
    --region asia-south1 `
    --project starry-runner-482513-c5 `
    --format "value(status.url)"

Write-Host "`n=== Deployment Complete! ===" -ForegroundColor Green
