export CORS_ALLOW_ORIGIN="http://localhost:5173;http://localhost:8080"

# Web search (dev default): SearXNG via localhost.
# If you're using the hp6 instance, run this tunnel first:
#   ssh -L 8082:127.0.0.1:8082 drawson@hp6
: "${ENABLE_WEB_SEARCH:=true}"
: "${WEB_SEARCH_ENGINE:=searxng}"
: "${SEARXNG_QUERY_URL:=http://127.0.0.1:8082/search}"

PORT="${PORT:-8080}"
uvicorn open_webui.main:app --port $PORT --host 0.0.0.0 --forwarded-allow-ips '*' --reload
