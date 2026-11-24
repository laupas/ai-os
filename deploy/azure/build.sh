#!/bin/sh
# Compiles main.bicep into azuredeploy.json, the file the "Deploy to Azure" button
# loads. Run it after every change to main.bicep and commit both; CI fails when
# they differ. The Bicep version is pinned, so the output only changes with the
# template. Without a local `az`, it runs in the Azure CLI image.
set -eu

BICEP_VERSION=v0.49.2
cd "$(dirname "$0")"

build='az bicep install --version '"$BICEP_VERSION"' >/dev/null 2>&1
az bicep build --file /tmp/main.bicep --stdout'

if command -v az >/dev/null 2>&1; then
  cp main.bicep /tmp/main.bicep
  sh -c "$build" > azuredeploy.json.new
else
  docker run --rm -i mcr.microsoft.com/azure-cli:latest \
    sh -c "cat > /tmp/main.bicep && $build" < main.bicep > azuredeploy.json.new
fi
mv azuredeploy.json.new azuredeploy.json
echo "wrote deploy/azure/azuredeploy.json"
