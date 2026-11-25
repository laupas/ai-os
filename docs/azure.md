# Running ai-os on Azure

ai-os runs as one container in an **Azure Web App** (App Service for Containers),
with its data on an **Azure Files** share mounted at `/data`. App Service gives you
HTTPS and a certificate; Slack and Teams need no inbound address (both use Socket
Mode), so the web console is the only thing App Service has to serve.

```
browser ──https──► Web App (ghcr.io/laupas/ai-os, 1 instance, Always On)
                     │  /data ──► Azure Files share "data"
                     └─► Slack, Teams, Anthropic (outbound only)
```

What it costs, roughly: a B2 plan (about USD 26/month) and a few GB of Azure Files
(cents).

## One click

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Flaupas%2Fai-os%2Fmain%2Fdeploy%2Fazure%2Fazuredeploy.json/createUIDefinitionUri/https%3A%2F%2Fraw.githubusercontent.com%2Flaupas%2Fai-os%2Fmain%2Fdeploy%2Fazure%2FcreateUiDefinition.json)

The portal asks for a resource group, a name for the web app, your name, address,
a console password and the secrets key, and optionally the Anthropic API key. It
creates the plan, the storage account with its share, and the web app as described below
([`deploy/azure/main.bicep`](../deploy/azure/main.bicep)). A few minutes later,
open `https://<name>.azurewebsites.net` and sign in with your address and that
password.

The console uses its own password login from the first start, so nobody can sign
in before you do. Afterwards:

- Change your password (Settings → Users), then delete the app setting
  `AIOS_OWNER_PASSWORD` (Web App → Environment variables). It is only read while no
  user has a password, but it need not stay there.
- For Microsoft 365 sign-in instead, register the application as in step 3 below,
  set its secret as the Variable `AIOS_SSO_MICROSOFT_SECRET` and switch under
  Settings → Login.
- Channels, the configuration remote and the rest: see step 6 below.

The **secrets key** is required: it encrypts the secrets ai-os stores on the share and
lives only in the web app's settings, so a copy of the share opens no secret. Generate
one before you start (`openssl rand -base64 48`) and save it in your password manager:
without it the stored secrets cannot be read. To replace it later (after a leak, say),
see [Secrets key](../README.md#secrets-key): the new key in `AIOS_SECRETS_KEY`, the old
one in `AIOS_SECRETS_KEY_PREVIOUS` (Web App → Environment variables), restart, then
remove the old one.

Redeploying the template to the same resource group leaves the share alone but
replaces the web app's settings with its own: settings you added in the portal
(Slack tokens, say) are gone, and the secrets key must be given again,
unchanged. Set channel tokens in the console instead, where they survive.

## By hand

The same with the `az` CLI, with Microsoft 365 sign-in from the start. Each step can
also be done in the portal.

### What you need

- The [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli), signed
  in (`az login`), and a subscription you may create resources in.
- An Anthropic API key (or a Claude subscription token, see **Claude** in the
  [README](../README.md#quick-start-docker)).
- Permission to register an application in your Microsoft Entra ID, for the login.
- Recommended: an empty private git repository for the configuration (GitHub,
  Azure DevOps, ...), so agents, skills and connectors are off-site as well.

### 1. Names

Pick your own names; the web app's name becomes `<name>.azurewebsites.net` and must
be unique in Azure, the storage account's name too (lowercase letters and digits).

```sh
RG=ai-os
LOCATION=westeurope
APP=ai-os-yourname
STORAGE=aiosyourname
URL=https://$APP.azurewebsites.net
```

### 2. Resource group, plan and storage

```sh
az group create --name $RG --location $LOCATION

# B2: 2 cores, 3.5 GB. B1 is too small for Claude and its MCP servers.
az appservice plan create --resource-group $RG --name $APP-plan \
  --is-linux --sku B2 --number-of-workers 1

az storage account create --resource-group $RG --name $STORAGE \
  --sku Standard_LRS --kind StorageV2 --min-tls-version TLS1_2
KEY=$(az storage account keys list --resource-group $RG --account-name $STORAGE \
  --query '[0].value' -o tsv)
az storage share-rm create --resource-group $RG --storage-account $STORAGE \
  --name data --quota 10
```

### 3. The login, before anything is reachable

A new ai-os lets whoever opens the console pick a user. On a public address that
must never happen, so the login is set up first: ai-os signs people in with their
Microsoft 365 account itself (`web.auth.mode: sso`).

Register the application in Entra ID:

```sh
TENANT=$(az account show --query tenantId -o tsv)
CLIENT_ID=$(az ad app create --display-name ai-os \
  --web-redirect-uris $URL/api/login/sso/callback \
  --sign-in-audience AzureADMyOrg --query appId -o tsv)
SSO_SECRET=$(az ad app credential reset --id $CLIENT_ID --append \
  --display-name ai-os --years 2 --query password -o tsv)
```

Then write the first configuration and put it on the share. `owner` is you, with
the address you sign in to Microsoft 365 with:

```sh
cat > config.yaml <<EOF
channels: [web]
timezone: Europe/Zurich

owner:
  name: Your Name
  accounts:
    - {channel: web, address: you@example.com}

web:
  public_url: $URL
  auth:
    mode: sso
    providers:
      - kind: microsoft
        tenant: $TENANT
        client_id: $CLIENT_ID
        client_secret_variable: AIOS_SSO_MICROSOFT_SECRET
EOF

az storage file upload --account-name $STORAGE --account-key "$KEY" \
  --share-name data --source config.yaml --path config.yaml
```

On the first start ai-os moves this file into its configuration repository as
`aios.yaml`; from then on it is edited on the console's Settings page.

If you clone an existing configuration instead (`AIOS_CONFIG_REMOTE` in step 5),
its `aios.yaml` wins and this file is ignored: make sure the `web.auth` there is
right for the new address.

### 4. The web app

```sh
az webapp create --resource-group $RG --plan $APP-plan --name $APP \
  --container-image-name ghcr.io/laupas/ai-os:latest
# It starts at once, with no data and no settings: stop it until it is set up.
az webapp stop --resource-group $RG --name $APP

az webapp config storage-account add --resource-group $RG --name $APP \
  --custom-id data --storage-type AzureFiles --account-name $STORAGE \
  --share-name data --access-key "$KEY" --mount-path /data

# Always On: otherwise App Service unloads the app when the console is idle, and
# with it the Slack and Teams connections and the triggers.
az webapp config set --resource-group $RG --name $APP --always-on true
az webapp update --resource-group $RG --name $APP --https-only true
```

Keep the plan at **one instance** and never turn on autoscale: two ai-os
instances would split the Slack and Teams messages between them.

### 5. Secrets and settings

App settings are encrypted at rest by App Service and reach ai-os as environment
variables, which it reads wherever a Variable is not set in the console.

```sh
az webapp config appsettings set --resource-group $RG --name $APP --settings \
  WEBSITES_PORT=8080 \
  WEBSITES_ENABLE_APP_SERVICE_STORAGE=false \
  AIOS_SECRETS_KEY="$(openssl rand -base64 48)" \
  ANTHROPIC_API_KEY="sk-ant-..." \
  AIOS_SSO_MICROSOFT_SECRET="$SSO_SECRET" \
  AIOS_VARIABLE_FILES_DIR=/tmp/aios-variable-files
```

- `AIOS_SECRETS_KEY` (required) encrypts the secrets ai-os stores on the share. Copy
  it from the portal (Web App → Environment variables) into your password manager:
  without it, a restored share cannot be read. Replace it only as in
  [Secrets key](../README.md#secrets-key).
- `AIOS_VARIABLE_FILES_DIR` keeps decrypted secret files on the container's own
  disk, not on the share.

Optional, all as further `--settings`:

| Setting | For |
|---|---|
| `AIOS_CONFIG_REMOTE`, `AIOS_CONFIG_TOKEN` (or `AIOS_CONFIG_SSH_KEY`) | push the configuration to your private repository; or, with an empty share, clone an existing configuration from it |
| `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN` | the Slack channel (see [Slack app](../README.md#slack-app)) |
| `TEAMS_APP_ID`, `TEAMS_APP_PASSWORD`, `TEAMS_TENANT_ID` | the Teams channel (see [Teams app](../README.md#teams-app)) |
| `RESEND_API_KEY`, `AIOS_MAIL_FROM` | sending mail |
| `OPENAI_API_KEY` | voice notes |

All of them can also be set later in the console instead.

### 6. Start and check

```sh
az webapp start --resource-group $RG --name $APP
az webapp log tail --resource-group $RG --name $APP
```

The first start pulls the image and takes a minute or two. The log shows the web
console listening on 8080. Then open `$URL`, sign in with Microsoft, and look at
the **Health** page: Claude's sign-in, the channels, the connectors.

Turn on channels under Settings → Channels, set up the configuration remote under
Settings → Git if you did not in step 5, and continue as in the
[Quick start](../README.md#quick-start-docker).

## Your own domain

```sh
az webapp config hostname add --resource-group $RG --webapp-name $APP \
  --hostname ai-os.example.com
az webapp config ssl create --resource-group $RG --name $APP \
  --hostname ai-os.example.com
az webapp config ssl bind --resource-group $RG --name $APP --ssl-type SNI \
  --certificate-thumbprint <thumbprint printed by the command above>
```

The first command needs a CNAME `ai-os.example.com → $APP.azurewebsites.net` and
the TXT record `asuid.ai-os` Azure asks for. Afterwards change `web.public_url` in
Settings → aios.yaml and add the new redirect address to the Entra application
(`<new url>/api/login/sso/callback`).

## Updating

`:latest` follows the `main` branch. A restart pulls the image again:

```sh
az webapp restart --resource-group $RG --name $APP
```

To stay on one version, use a version tag (`ghcr.io/laupas/ai-os:2.0`) and change
it when you want to move on:

```sh
az webapp config container set --resource-group $RG --name $APP \
  --container-image-name ghcr.io/laupas/ai-os:2.1
```

## Backups

Everything is on the share: users, memories, conversations, connector sign-ins and
the configuration repository. Protect it with Azure Backup for file shares
(Storage account → Data protection), or take snapshots by hand:

```sh
az storage share snapshot --account-name $STORAGE --account-key "$KEY" --name data
```

With a configuration remote, agents, skills, connectors and triggers are also in
your git repository after every change.

## Good to know

- **Restarts** (an update, a changed app setting, Azure's own maintenance) interrupt
  conversations in progress, nothing else. App Service may start the new container
  shortly before it stops the old one; for those seconds a Slack or Teams message
  can reach the one about to stop.
- **Playwright and Signal**, which run next to ai-os in the Docker setup, are
  sidecar containers on App Service (Web App → Deployment Center → Containers).
  Not covered here.
- **Removing everything**: `az group delete --name $RG` and
  `az ad app delete --id $CLIENT_ID`.
