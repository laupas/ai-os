// ai-os as an Azure Web App, its data on an Azure Files share mounted at /data.
// The "Deploy to Azure" button uses azuredeploy.json, compiled from this file:
//   az bicep build --file main.bicep --outfile azuredeploy.json
// See docs/azure.md.

@description('Name of the web app: it becomes <name>.azurewebsites.net and must be unique in Azure.')
@minLength(2)
@maxLength(60)
param appName string

@description('Where everything is created.')
param location string = resourceGroup().location

@description('Your name, as ai-os shows it.')
param ownerName string

@description('Your address: the name you sign in to the console with.')
param ownerEmail string

@description('Your first console password, at least 12 characters. Change it in the console afterwards.')
@minLength(12)
@secure()
param ownerPassword string

@description('Anthropic API key. Leave empty to set it (or a Claude subscription token) in the console.')
@secure()
param anthropicApiKey string = ''

@description('Encrypts the secrets ai-os stores. Leave empty to have one generated onto the share; set your own to keep it apart from the data. Never change it afterwards.')
@secure()
param secretsKey string = ''

@description('Time zone for triggers and dates, e.g. Europe/Zurich.')
param timezone string = 'UTC'

@description('Size of the App Service plan. B1 is too small for Claude and its MCP servers.')
@allowed(['B2', 'B3', 'P0v3', 'P1v3'])
param sku string = 'B2'

@description('The ai-os image.')
param image string = 'ghcr.io/laupas/ai-os:latest'

var url = 'https://${appName}.azurewebsites.net'
var storageName = take('aios${uniqueString(resourceGroup().id, appName)}', 24)

// The first config.yaml: the owner and a password login, so nobody else can sign in
// before you do. ai-os takes it into its configuration repository on the first start.
var initialConfig = {
  channels: ['web']
  timezone: timezone
  owner: {
    name: ownerName
    accounts: [{ channel: 'web', address: ownerEmail }]
  }
  web: {
    public_url: url
    auth: { mode: 'password' }
  }
}

var baseSettings = [
  { name: 'WEBSITES_PORT', value: '8080' }
  { name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE', value: 'false' }
  { name: 'AIOS_INITIAL_CONFIG', value: string(initialConfig) }
  { name: 'AIOS_OWNER_PASSWORD', value: ownerPassword }
  // Decrypted secret files stay on the container's own disk, not on the share.
  { name: 'AIOS_VARIABLE_FILES_DIR', value: '/tmp/aios-variable-files' }
]
var optionalSettings = concat(
  empty(anthropicApiKey) ? [] : [{ name: 'ANTHROPIC_API_KEY', value: anthropicApiKey }],
  empty(secretsKey) ? [] : [{ name: 'AIOS_SECRETS_KEY', value: secretsKey }]
)

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
  }
}

resource files 'Microsoft.Storage/storageAccounts/fileServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource share 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  parent: files
  name: 'data'
  properties: { shareQuota: 10 }
}

resource plan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${appName}-plan'
  location: location
  kind: 'linux'
  // One instance, never more: two would split the Slack and Teams messages.
  sku: { name: sku, capacity: 1 }
  properties: { reserved: true }
}

resource app 'Microsoft.Web/sites@2023-12-01' = {
  name: appName
  location: location
  kind: 'app,linux,container'
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'DOCKER|${image}'
      // Otherwise App Service unloads an idle app, and with it Slack, Teams and the triggers.
      alwaysOn: true
      numberOfWorkers: 1
      http20Enabled: true
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: concat(baseSettings, optionalSettings)
      azureStorageAccounts: {
        data: {
          type: 'AzureFiles'
          accountName: storage.name
          shareName: share.name
          mountPath: '/data'
          accessKey: storage.listKeys().keys[0].value
        }
      }
    }
  }
}

output url string = url
output storageAccount string = storage.name
