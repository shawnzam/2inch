#!/usr/bin/env bash
# Deploy 2" (two inch) to Cloudflare Pages.
# Auth: reads a scoped API token from ~/.cf_2inch_token (Account>Pages>Edit, Zone>DNS>Edit on 2inch.fm).
set -euo pipefail

TOKEN_FILE="$HOME/.cf_2inch_token"
if [ ! -s "$TOKEN_FILE" ]; then
  echo "Missing $TOKEN_FILE — create a Cloudflare API token and: printf '%s' 'TOKEN' > $TOKEN_FILE && chmod 600 $TOKEN_FILE" >&2
  exit 1
fi

export CLOUDFLARE_API_TOKEN="$(cat "$TOKEN_FILE")"
export CLOUDFLARE_ACCOUNT_ID="37fb40649f6dbbb1625fc0b876103f6f"

cd "$(dirname "$0")"
npx wrangler pages deploy indie-index --project-name=2inch --branch=main

echo
echo "Live: https://2inch.fm  ·  https://2inch.pages.dev"
