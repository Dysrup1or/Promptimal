# 🚀 PROMPTLY 3.0 - COMPLETE RAILWAY DEPLOYMENT GUIDE

## For First-Time Deployers | Verified December 8, 2025

---

## TABLE OF CONTENTS

1. [Prerequisites Checklist](#1-prerequisites-checklist)
2. [Step 1: Prepare Your Local Repository](#step-1-prepare-your-local-repository)
3. [Step 2: Create GitHub Repository](#step-2-create-github-repository)
4. [Step 3: Push Code to GitHub](#step-3-push-code-to-github)
5. [Step 4: Create Railway Account](#step-4-create-railway-account)
6. [Step 5: Create New Railway Project](#step-5-create-new-railway-project)
7. [Step 6: Add PostgreSQL Database](#step-6-add-postgresql-database)
8. [Step 7: Configure Environment Variables](#step-7-configure-environment-variables)
9. [Step 8: Deploy the Application](#step-8-deploy-the-application)
10. [Step 9: Verify Deployment](#step-9-verify-deployment)
11. [Step 10: Set Up Custom Domain (Optional)](#step-10-set-up-custom-domain-optional)
12. [Troubleshooting Guide](#troubleshooting-guide)
13. [Ongoing Maintenance](#ongoing-maintenance)
14. [Cost Estimation](#cost-estimation)

---

## 1. PREREQUISITES CHECKLIST

Before starting, ensure you have:

### Accounts Needed
- [ ] **GitHub account** - Free at https://github.com/signup
- [ ] **Railway account** - Free tier at https://railway.app (requires GitHub)
- [ ] **Gemini API Key** - Free at https://makersuite.google.com/app/apikey
- [ ] **DeepSeek API Key** - At https://platform.deepseek.com/api_keys (requires $5 deposit)

### Software Installed
- [ ] **Git** - Verify: `git --version` (should show version 2.x+)
- [ ] **Python 3.11** - Verify: `python --version` (should show 3.11.x)

### Project Ready
- [ ] All tests passing: `python -m pytest tests/test_v2.py -v` (27/27 pass)
- [ ] `.env` file exists with your API keys (local testing)
- [ ] `.gitignore` includes `.env` (CRITICAL - never commit secrets!)

---

## STEP 1: PREPARE YOUR LOCAL REPOSITORY

### 1.1 Open PowerShell and Navigate to Project

```powershell
cd C:\Users\alexe\Promptimal
```

### 1.2 Verify Git Status

```powershell
git status
```

You should see a list of modified/untracked files.

### 1.3 Stage All Changes

```powershell
git add .
```

### 1.4 Verify Sensitive Files Are NOT Staged

**CRITICAL SECURITY CHECK:**

```powershell
git status
```

**VERIFY these files are NOT in the "Changes to be committed" list:**
- `.env` ❌ (contains API keys - NEVER commit)
- `data/` ❌ (contains user database)
- `logs/` ❌ (may contain sensitive info)
- `.prompt_cache/` ❌ (cached data)

If any of these appear, run:
```powershell
git reset HEAD .env
git reset HEAD data/
git reset HEAD logs/
git reset HEAD .prompt_cache/
```

### 1.5 Commit Your Changes

```powershell
git commit -m "Production-ready: Auth, rate limiting, Railway config"
```

**Expected output:** `[main xxxxxxx] Production-ready: Auth, rate limiting, Railway config`

---

## STEP 2: CREATE GITHUB REPOSITORY

### 2.1 Go to GitHub

Open your browser and go to: **https://github.com/new**

### 2.2 Create New Repository

Fill in the form:

| Field | Value |
|-------|-------|
| **Repository name** | `Promptimal` (or `promptly-app`) |
| **Description** | `AI-Powered Prompt Engineering Platform` |
| **Visibility** | `Private` (recommended for production apps) |
| **Initialize with README** | ❌ **UNCHECKED** (we already have files) |
| **Add .gitignore** | ❌ **UNCHECKED** (we already have one) |
| **Choose a license** | None (we already have code) |

### 2.3 Click "Create repository"

You'll see a page with instructions. **COPY the HTTPS URL** that looks like:
```
https://github.com/YOUR_USERNAME/Promptimal.git
```

---

## STEP 3: PUSH CODE TO GITHUB

### 3.1 Add GitHub as Remote

Back in PowerShell, run (replace with YOUR URL):

```powershell
git remote add origin https://github.com/YOUR_USERNAME/Promptimal.git
```

### 3.2 Verify Remote Added

```powershell
git remote -v
```

**Expected output:**
```
origin  https://github.com/YOUR_USERNAME/Promptimal.git (fetch)
origin  https://github.com/YOUR_USERNAME/Promptimal.git (push)
```

### 3.3 Push to GitHub

```powershell
git push -u origin main
```

**If prompted for credentials:**
- Username: Your GitHub username
- Password: Your GitHub **Personal Access Token** (NOT your password!)

**To create a Personal Access Token:**
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Give it a name like "Promptimal Deploy"
4. Select scopes: `repo` (full control)
5. Click "Generate token"
6. **COPY THE TOKEN** (you won't see it again!)
7. Use this token as your password

### 3.4 Verify Push Successful

Go to `https://github.com/YOUR_USERNAME/Promptimal` in your browser.

**You should see all your files listed.**

✅ **Checkpoint: Code is now on GitHub!**

---

## STEP 4: CREATE RAILWAY ACCOUNT

### 4.1 Go to Railway

Open: **https://railway.app**

### 4.2 Sign Up with GitHub

1. Click **"Login"** (top right)
2. Click **"Login with GitHub"**
3. Authorize Railway to access your GitHub account
4. Complete any verification steps

### 4.3 Verify Account

Railway may require:
- Email verification
- GitHub account age verification (must be 30+ days old)

If your GitHub is new, you may need to add a payment method to unlock deployments.

---

## STEP 5: CREATE NEW RAILWAY PROJECT

### 5.1 Go to Dashboard

After login, you should be at: **https://railway.app/dashboard**

### 5.2 Create New Project

1. Click **"New Project"** button (or "+ New" in top right)

### 5.3 Select Deployment Method

You'll see options:
- **Deploy from GitHub repo** ← Select this one
- Empty project
- Template

### 5.4 Connect GitHub Repository

1. Click **"Deploy from GitHub repo"**
2. If prompted, authorize Railway to access your repositories
3. Find and select **"Promptimal"** (or your repo name)
4. Click **"Deploy Now"**

**⚠️ DON'T WAIT FOR IT TO FINISH YET!** It will fail because we need to add the database and environment variables first.

---

## STEP 6: ADD POSTGRESQL DATABASE

### 6.1 Add Database Service

While in your Railway project:

1. Click **"+ New"** button in the project canvas
2. Select **"Database"**
3. Select **"Add PostgreSQL"**

### 6.2 Wait for Database Creation

Railway will provision a PostgreSQL database. This takes 30-60 seconds.

### 6.3 Verify Database Connection

1. Click on the **PostgreSQL** service in your canvas
2. Go to the **"Variables"** tab
3. You should see variables like:
   - `DATABASE_URL`
   - `PGHOST`
   - `PGPASSWORD`
   - `PGUSER`
   - `PGDATABASE`
   - `PGPORT`

**The `DATABASE_URL` is the important one** - Railway will automatically make this available to your app.

---

## STEP 7: CONFIGURE ENVIRONMENT VARIABLES

### 7.1 Select Your App Service

1. Click on your **main application service** (not the database) - it should show your GitHub repo name
2. Go to the **"Variables"** tab

### 7.2 Add Required Environment Variables

Click **"+ New Variable"** for each:

| Variable Name | Value | Notes |
|--------------|-------|-------|
| `GEMINI_API_KEY` | `your-actual-gemini-key` | From Google AI Studio |
| `DEEPSEEK_API_KEY` | `your-actual-deepseek-key` | From DeepSeek Platform |

### 7.3 Reference Database URL

The `DATABASE_URL` is automatically available from the PostgreSQL service. To ensure it's linked:

1. Click **"+ New Variable"**
2. For the value, click **"Add Reference"**
3. Select your PostgreSQL service
4. Select `DATABASE_URL`
5. This creates: `DATABASE_URL = ${{Postgres.DATABASE_URL}}`

**Your app automatically detects `DATABASE_URL` and uses PostgreSQL instead of SQLite!**

### 7.4 (Optional) Add Logging Level

| Variable Name | Value |
|--------------|-------|
| `LOG_LEVEL` | `INFO` |

---

## STEP 8: DEPLOY THE APPLICATION

### 8.1 Trigger Redeploy

Now that environment variables are set:

1. Click on your app service
2. Go to **"Deployments"** tab
3. Click **"Redeploy"** on the latest deployment (or it may auto-redeploy)

### 8.2 Watch the Build Logs

1. Click on the active deployment
2. Watch the **Build Logs**

**Expected log progression:**
```
━━━━━━━━━ Building ━━━━━━━━━
Nixpacks was unable to generate a build plan for this app
Using Procfile
...
Installing pip packages...
✔ Successfully installed packages
...
━━━━━━━━━ Deploying ━━━━━━━━━
Starting: streamlit run app.py --server.port=$PORT...
You can now view your Streamlit app in your browser.
```

### 8.3 Wait for Deployment

Build typically takes **2-5 minutes**. 

**Success indicators:**
- Status changes to **"Success"** (green checkmark)
- "Active" label appears on deployment

---

## STEP 9: VERIFY DEPLOYMENT

### 9.1 Get Your App URL

1. Click on your app service
2. Go to **"Settings"** tab
3. Under **"Domains"**, you'll see a URL like:
   ```
   promptimal-production.up.railway.app
   ```

Or click **"Generate Domain"** if none exists.

### 9.2 Open Your App

Click the URL or copy it to your browser.

### 9.3 Test Core Functionality

**Test #1: Registration**
1. Click "Register" tab
2. Fill in: email, first name, last name, password
3. Click "Create Account"
4. ✅ **Expected:** Success message, auto-login

**Test #2: Pipeline (requires API keys working)**
1. Enter a prompt idea: "Write a prompt for summarizing articles"
2. Click "🔧 Optimize Prompt"
3. ✅ **Expected:** Spinner, then optimized prompt appears

**Test #3: Rate Limiting**
1. Check sidebar - should show "99 requests remaining" (after 1 use)
2. ✅ **Expected:** Usage counter decrements

**Test #4: Logout/Login**
1. Click "🚪 Logout"
2. Login with your credentials
3. ✅ **Expected:** Previous usage persists (database working!)

---

## STEP 10: SET UP CUSTOM DOMAIN (OPTIONAL)

### 10.1 Add Custom Domain

If you own a domain (e.g., `promptly.yourdomain.com`):

1. Go to your app service **"Settings"** tab
2. Under **"Domains"**, click **"+ Custom Domain"**
3. Enter your domain: `promptly.yourdomain.com`
4. Railway will show DNS records to add

### 10.2 Configure DNS

At your domain registrar (Cloudflare, Namecheap, etc.):

Add a **CNAME record**:
| Type | Name | Target |
|------|------|--------|
| CNAME | `promptly` | `your-app.up.railway.app` |

### 10.3 Wait for DNS Propagation

Takes 5 minutes to 24 hours depending on registrar.

---

## TROUBLESHOOTING GUIDE

### Issue: Build Fails with "Module not found"

**Cause:** Missing dependency in requirements.txt

**Fix:**
1. Check build logs for the missing module
2. Add to `requirements.txt`
3. Push to GitHub: `git add . && git commit -m "fix deps" && git push`
4. Railway auto-redeploys

---

### Issue: App Crashes on Startup

**Cause:** Usually missing environment variables

**Check:**
1. Go to Variables tab
2. Verify `GEMINI_API_KEY` and `DEEPSEEK_API_KEY` are set
3. Verify `DATABASE_URL` is linked

**View Logs:**
1. Go to Deployments tab
2. Click latest deployment
3. Check "Deploy Logs" for error messages

---

### Issue: "Connection refused" or Database Errors

**Cause:** DATABASE_URL not properly linked

**Fix:**
1. Delete the `DATABASE_URL` variable
2. Re-add it using "Add Reference" → PostgreSQL → DATABASE_URL
3. Redeploy

---

### Issue: "Invalid API Key" Errors

**Cause:** API key incorrect or has extra spaces

**Fix:**
1. Go to Variables tab
2. Delete and re-add the API key
3. Ensure NO spaces before/after the key
4. Redeploy

---

### Issue: Login Works But Data Doesn't Persist

**Cause:** Using SQLite instead of PostgreSQL

**Check:**
1. In Variables, verify `DATABASE_URL` exists
2. Check logs for "Using PostgreSQL" message
3. If missing, add DATABASE_URL reference

---

### Issue: Railway Shows "Your project is sleeping"

**Cause:** Free tier has limits

**Fix:**
- Upgrade to paid tier ($5/month)
- Or accept sleep behavior (app wakes on request, ~10s delay)

---

## ONGOING MAINTENANCE

### Deploying Updates

After making code changes locally:

```powershell
cd C:\Users\alexe\Promptimal
git add .
git commit -m "Description of changes"
git push
```

Railway **automatically deploys** when you push to main branch.

### Monitoring

1. **Logs:** Railway dashboard → Your service → Deployments → View Logs
2. **Metrics:** Railway shows CPU, memory, network usage
3. **Database:** Click PostgreSQL service to see stats

### Backups

Railway PostgreSQL includes automatic backups. To export:

1. Click PostgreSQL service
2. Go to "Connect" tab
3. Use the connection string with `pg_dump` locally

---

## COST ESTIMATION

### Railway Pricing (as of Dec 2025)

| Resource | Free Tier | Hobby ($5/mo) |
|----------|-----------|---------------|
| **Compute** | 500 hours/month | Unlimited |
| **Memory** | 512MB | 8GB |
| **Database** | 1GB storage | 10GB storage |
| **Network** | 100GB/month | Unlimited |
| **Sleep** | After 30min inactive | Never sleeps |

### Estimated Monthly Cost

| Tier | Users | Estimated Cost |
|------|-------|----------------|
| Development/Testing | 1-5 | **$0** (Free tier) |
| Small Production | 10-50 | **$5-10/month** |
| Growing | 50-500 | **$15-25/month** |

### LLM API Costs (Separate from Railway)

| API | Cost | Monthly Estimate (100 users × 50 requests) |
|-----|------|-------------------------------------------|
| Gemini | Free | $0 |
| DeepSeek | $0.0012/request avg | ~$6/month |

---

## 🎉 DEPLOYMENT COMPLETE!

Your Promptly 3.0 application is now live on Railway with:

- ✅ **PostgreSQL database** for persistent user data
- ✅ **Automatic HTTPS** (SSL certificate)
- ✅ **Auto-deploys** on git push
- ✅ **Environment variable security** (secrets never in code)
- ✅ **Horizontal scaling** ready (Railway handles it)

### Quick Links to Save

| Resource | URL |
|----------|-----|
| Your App | `https://YOUR-APP.up.railway.app` |
| Railway Dashboard | https://railway.app/dashboard |
| GitHub Repo | `https://github.com/YOUR_USERNAME/Promptimal` |

---

## QUICK REFERENCE COMMANDS

```powershell
# Check status
git status

# Stage all changes
git add .

# Commit with message
git commit -m "Your message here"

# Push to deploy
git push

# View recent commits
git log --oneline -5

# Pull latest (if editing on multiple machines)
git pull
```

---

*Guide created December 8, 2025 | Verified against Railway's current interface*
