#!/usr/bin/env bash
# ==============================================================================
# BABA MILK - TRIGGER AUTOMATIC WHATSAPP CALL
# Reads PHONE_NUMBER_ID and WHATSAPP_TOKEN automatically from agent/.env or server/.env
# Usage: ./trigger_call.sh [PHONE_NUMBER]
# Example: ./trigger_call.sh 917889142708
# ==============================================================================

set -euo pipefail

PHONE="${1:-917889142708}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Clean phone number (strip + and spaces)
PHONE="$(echo "$PHONE" | tr -d '+ -')"

# Load environment variables
AGENT_ENV="$SCRIPT_DIR/agent/.env"
SERVER_ENV="$(dirname "$SCRIPT_DIR")/server/.env"

if [ -f "$AGENT_ENV" ]; then
  # Load non-comment lines
  export $(grep -E '^[A-Za-z0-9_]+=' "$AGENT_ENV" | xargs -d '\n')
elif [ -f "$SERVER_ENV" ]; then
  export $(grep -E '^[A-Za-z0-9_]+=' "$SERVER_ENV" | xargs -d '\n')
fi

PHONE_NUMBER_ID="${PHONE_NUMBER_ID:-1288371367698715}"
ACCESS_TOKEN="${WHATSAPP_TOKEN:-}"

if [ -z "$ACCESS_TOKEN" ]; then
  echo "❌ Error: WHATSAPP_TOKEN is missing in agent/.env or server/.env"
  exit 1
fi

echo "=================================================================="
echo "📞 Baba Milk - Initiating Automatic WhatsApp Call"
echo "🔹 Target:           $PHONE"
echo "🔹 Phone Number ID:  $PHONE_NUMBER_ID"
echo "=================================================================="

# Method 1: Initiate WhatsApp Call via Meta Cloud API
# Meta connects the user on WhatsApp and bridges them to your Asterisk server
echo "🚀 Dispatching call via Meta WhatsApp Calling API..."
RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "https://graph.facebook.com/v21.0/${PHONE_NUMBER_ID}/calls" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"messaging_product\": \"whatsapp\",
    \"to\": \"${PHONE}\",
    \"action\": \"connect\"
  }")

HTTP_STATUS=$(echo "$RESPONSE" | grep "HTTP_STATUS" | cut -d':' -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_STATUS")

echo "Meta Response (HTTP $HTTP_STATUS):"
echo "$BODY"

# Method 2: Also drop an Asterisk spool file as backup / direct trunk
OUTGOING_DIR="$SCRIPT_DIR/outgoing"
mkdir -p "$OUTGOING_DIR"
TIMESTAMP="$(date +%s)"
CALL_FILE_TEMP="/tmp/call_${PHONE}_${TIMESTAMP}.call"
CALL_FILE_DEST="$OUTGOING_DIR/call_${PHONE}_${TIMESTAMP}.call"

cat << EOF > "$CALL_FILE_TEMP"
Channel: PJSIP/whatsapp-outbound/sip:${PHONE}@wa.meta.vc:5061
CallerID: "Baba Milk" <+${PHONE_NUMBER_ID}>
MaxRetries: 2
RetryTime: 30
WaitTime: 45
Context: whatsapp-outbound
Extension: ${PHONE}
Priority: 1
EOF

chmod 666 "$CALL_FILE_TEMP"
mv "$CALL_FILE_TEMP" "$CALL_FILE_DEST"

echo "✅ Trigger complete! When answered, Asterisk will play the welcome message and connect Shreya AI."
