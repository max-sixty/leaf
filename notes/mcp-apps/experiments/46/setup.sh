#!/bin/bash
set -e
git clone https://github.com/modelcontextprotocol/ext-apps.git /Users/maximilian/workspace/leaf-ext-apps-reference
git -C /Users/maximilian/workspace/leaf-ext-apps-reference checkout 10195ad91851502134930e9b80ec2c04e277a720
(
  cd /Users/maximilian/workspace/leaf-ext-apps-reference
  /opt/homebrew/bin/node /opt/homebrew/lib/node_modules/npm/bin/npm-cli.js ci --silent
  /opt/homebrew/bin/node /opt/homebrew/lib/node_modules/npm/bin/npm-cli.js run build --workspace @modelcontextprotocol/ext-apps-basic-host
)
