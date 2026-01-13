# GitHub Actions Secrets Setup

Follow these steps to set up the required secrets for GitHub Actions deployment.

## Step 1: Create Azure Service Principal

Run this command in your terminal to create a service principal for GitHub Actions:

```bash
az ad sp create-for-rbac \
  --name "github-actions-chuuk" \
  --role contributor \
  --scopes /subscriptions/$(az account show --query id -o tsv)/resourceGroups/rg-chuuk-beta-eastus2 \
  --sdk-auth
```

This will output JSON like:
```json
{
  "clientId": "xxx",
  "clientSecret": "xxx",
  "subscriptionId": "xxx",
  "tenantId": "xxx",
  ...
}
```

**Copy this entire JSON output** - you'll need it for the next step.

## Step 2: Add Secrets to GitHub

Go to your GitHub repository:
1. Click **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Add each secret below:

### Required Secrets:

#### 1. AZURE_CREDENTIALS
- **Name:** `AZURE_CREDENTIALS`
- **Value:** The entire JSON output from Step 1

#### 2. GOOGLE_CLOUD_API_KEY
- **Name:** `GOOGLE_CLOUD_API_KEY`
- **Value:** Your Google Cloud Translation API key
- **Where to find it:** Check your `.env` file or Google Cloud Console

#### 3. FLASK_SECRET_KEY
- **Name:** `FLASK_SECRET_KEY`
- **Value:** Generate a new one with this command:
```bash
openssl rand -hex 32
```
- Copy the output and use it as the secret value

## Step 3: Verify Secrets

After adding all three secrets, you should see them listed in:
**Settings** → **Secrets and variables** → **Actions**

✅ AZURE_CREDENTIALS
✅ GOOGLE_CLOUD_API_KEY
✅ FLASK_SECRET_KEY

## Step 4: Test the Workflow

1. Go to **Actions** tab in your GitHub repository
2. Click **Deploy Main Dictionary App** workflow
3. Click **Run workflow**
4. Add a reason (optional) like "Testing GitHub Actions deployment"
5. Click **Run workflow** button

Watch the deployment progress in real-time!

## Troubleshooting

### "Azure Login Failed"
- Check that AZURE_CREDENTIALS JSON is complete and valid
- Verify the service principal has contributor access to the resource group

### "Google API key not set"
- Verify GOOGLE_CLOUD_API_KEY secret is set correctly
- No quotes needed in the secret value

### "Cosmos DB access denied"
- The service principal needs permission to read Cosmos DB keys
- The script fetches keys dynamically, so this should work automatically

## Next Steps

Once manual deployment works:
1. You can enable auto-deploy by changing `workflow_dispatch` to `push` in the workflow file
2. Add deployment status badge to README
3. Set up Ollama deployment workflow (optional)
