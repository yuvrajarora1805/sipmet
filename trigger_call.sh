#!/usr/bin/env bash
# ==============================================================================
# BABA MILK - TRIGGER AUTOMATIC OUTBOUND WHATSAPP CALL
# Usage: ./trigger_call.sh <PHONE_NUMBER> [CALLER_ID]
# Example: ./trigger_call.sh 917889142708
# ==============================================================================

set -euo pipefail

PHONE="${1:-917889142708}"
CALLER_ID="${2:-Baba Milk <+917889142708>}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTGOING_DIR="$SCRIPT_DIR/outgoing"
mkdir -p "$OUTGOING_DIR"

# Clean phone number (strip + and spaces)
PHONE="$(echo "$PHONE" | tr -d '+ -')"

TIMESTAMP="$(date +%s)"
CALL_FILE_TEMP="/tmp/call_${PHONE}_${TIMESTAMP}.call"
CALL_FILE_DEST="$OUTGOING_DIR/call_${PHONE}_${TIMESTAMP}.call"

echo "📞 Triggering automatic WhatsApp call to: $PHONE"

cat << EOF > "$CALL_FILE_TEMP"
Channel: PJSIP/sip:${PHONE}@wa.meta.vc:5061
CallerID: ${CALLER_ID}
MaxRetries: 2
RetryTime: 30
WaitTime: 45
Context: whatsapp-outbound
Extension: ${PHONE}
Priority: 1
EOF

# Ensure file has proper permissions
chmod 666 "$CALL_FILE_TEMP"

# Atomic move triggers Asterisk immediately
mv "$CALL_FILE_TEMP" "$CALL_FILE_DEST"

echo "✅ Call queued! Asterisk will dial $PHONE via Meta WhatsApp Calling."
echo "   When answered, it will play the welcome message and connect Shreya AI."
