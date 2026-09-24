#!/bin/bash
BOOTSTRAP="localhost:9092"
TOPICS=(
  "talent-assessments"
  "talent-score-updates"
  "talent-placements"
  "sit.enrollments"
  "sit.ecitizen"
  "sit.credentials"
  "sit.membership-checkins"
  "ar.actions"
  "ar.approvals"
  "ford.membership.registrations"
  "ford.membership.verified"
  "ford.primary.ballots"
)
for t in "${TOPICS[@]}"; do
  /opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BOOTSTRAP" \
    --create --topic "$t" --partitions 3 --replication-factor 3 \
    --if-not-exists 2>&1 && echo "OK: $t" || echo "ERR: $t"
done

echo "==> Listing all topics..."
/opt/kafka/bin/kafka-topics.sh --bootstrap-server "$BOOTSTRAP" --list | grep -E "talent|sit\.|ar\.|ford\."
