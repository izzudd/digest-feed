#!/usr/bin/env bash
# Publish one issue: build EPUB -> refresh index/OPDS -> push -> deploy -> verify.
# Usage: bash tools/publish.sh 2026-11-25
set -euo pipefail

DATE="${1:?usage: publish.sh YYYY-MM-DD}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="$PATH:/opt/data/.local/bin"

APP_UUID="03zvx5x4ngsk4p0hz0j5mwja"
BASE="https://feed.izzudd.my.id"
FILE="public/epubs/zud-daily-$DATE.epub"

[ -f "issues/$DATE.json" ] || { echo "missing issues/$DATE.json"; exit 1; }

echo "== build"
python3 tools/digest.py build "issues/$DATE.json"

echo "== sanity check the epub"
python3 - "$FILE" <<'PY'
import sys, zipfile
p = sys.argv[1]
z = zipfile.ZipFile(p)
assert z.read("mimetype") == b"application/epub+zip", "bad mimetype"
opf = z.read("OEBPS/content.opf").decode()
assert "<dc:language>" in opf and "dc:title" in opf
chapters = [n for n in z.namelist() if n.startswith("OEBPS/") and n.endswith(".xhtml")]
print(f"   ok: {len(chapters)} xhtml pages, {len(open(p,'rb').read())/1024:.0f} KB")
PY

echo "== commit + push"
git add -A
if git diff --cached --quiet; then
  echo "   nothing to commit"
else
  git -c user.email=izzudd@users.noreply.github.com -c user.name="Hermes" \
      commit -qm "digest $DATE"
  git push -q origin main
  echo "   pushed $(git rev-parse --short HEAD)"
fi

echo "== deploy"
TOKEN="$(grep -oP '(?<=^MCP_COOLIFY_API_KEY=).*' /opt/data/.env)"
API="https://cool.izzudd.my.id/api/v1"
RESP="$(curl -s -X POST -H "Authorization: Bearer $TOKEN" \
        -H "Accept: application/json" \
        "$API/deploy?uuid=$APP_UUID&force=false")"
DEP="$(printf '%s' "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin).get('deployments',[{}])[0].get('deployment_uuid',''))")"
echo "   deployment: ${DEP:-none}"

if [ -n "$DEP" ]; then
  for i in $(seq 1 40); do
    sleep 6
    ST="$(curl -s -H "Authorization: Bearer $TOKEN" "$API/deployments/$DEP" \
          | python3 -c "import sys,json;print(json.load(sys.stdin).get('status',''))")"
    [ "$ST" = "finished" ] && { echo "   deploy finished"; break; }
    case "$ST" in failed|error|cancelled) echo "   deploy $ST"; exit 1;; esac
    echo "   ... $ST"
  done
fi

echo "== verify live"
for u in "/epubs/zud-daily-$DATE.epub" "/latest.epub" "/opds"; do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$BASE$u")"
  echo "   $u -> $code"
  [ "$code" = "200" ] || exit 1
done
curl -s "$BASE/opds" | grep -q "zud-daily-$DATE.epub" || { echo "   opds does not list the new issue"; exit 1; }
echo "OK: $BASE/epubs/zud-daily-$DATE.epub"
