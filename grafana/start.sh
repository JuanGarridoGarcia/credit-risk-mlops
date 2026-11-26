#!/bin/sh
# Grafana's start (D-148): writes the contact point of the channels that are set, then
# hands over to the image's own start. The file is written inside the container only,
# never in the repository, so the token is never in git. Telegram when its token and
# chat are set; a webhook when GRAFANA_WEBHOOK_URL is set (the tests' receiver, T32.4).
# With neither, Grafana starts without a channel and without the policy: the dashboards
# work the same.
set -eu
target=/etc/grafana/provisioning/alerting
mkdir -p "$target"
cp /etc/grafana/alerting/rules.yaml "$target/rules.yaml"
receivers=""
if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
  receivers="$receivers
      - uid: credit-risk-telegram
        type: telegram
        disableResolveMessage: true
        settings:
          bottoken: '${TELEGRAM_BOT_TOKEN}'
          chatid: '${TELEGRAM_CHAT_ID}'"
fi
if [ -n "${GRAFANA_WEBHOOK_URL:-}" ]; then
  receivers="$receivers
      - uid: credit-risk-webhook
        type: webhook
        disableResolveMessage: true
        settings:
          url: '${GRAFANA_WEBHOOK_URL}'
          httpMethod: POST"
fi
# Grafana keeps what it provisioned in its database (the volume): a channel no longer
# set is deleted explicitly, or it would stay from an earlier start.
deletions=""
[ -z "${TELEGRAM_BOT_TOKEN:-}" ] || [ -z "${TELEGRAM_CHAT_ID:-}" ] &&
  deletions="$deletions
  - orgId: 1
    uid: credit-risk-telegram"
[ -z "${GRAFANA_WEBHOOK_URL:-}" ] &&
  deletions="$deletions
  - orgId: 1
    uid: credit-risk-webhook"
rm -f "$target/contactpoints.yaml" "$target/policies.yaml" "$target/deletions.yaml"
if [ -n "$receivers" ]; then
  printf 'apiVersion: 1\n\ncontactPoints:\n  - orgId: 1\n    name: credit-risk\n    receivers:%s\n' \
    "$receivers" > "$target/contactpoints.yaml"
  cp /etc/grafana/alerting/policies.yaml "$target/policies.yaml"
  [ -z "$deletions" ] ||
    printf 'apiVersion: 1\n\ndeleteContactPoints:%s\n' "$deletions" > "$target/deletions.yaml"
  echo "start.sh: contact point with$( [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && echo ' telegram')$( [ -n "${GRAFANA_WEBHOOK_URL:-}" ] && echo ' webhook')"
else
  # No channel: back to the default policy, then no contact point of ours.
  printf 'apiVersion: 1\n\nresetPolicies:\n  - 1\n\ndeleteContactPoints:%s\n' "$deletions" \
    > "$target/deletions.yaml"
  echo "start.sh: no channel set; alerts are only shown"
fi
exec /run.sh "$@"
