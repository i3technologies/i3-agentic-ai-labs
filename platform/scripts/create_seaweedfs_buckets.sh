#!/bin/sh
# Create SeaweedFS buckets via S3 API using wget
S3="http://localhost:8333"
BUCKETS="talent-cvs talent-certs talent-reports sit-course-content sit-exam-assets sit-professional-docs sit-credentials ar-context ford-evidence"

for b in $BUCKETS; do
  wget -q -O /dev/null --method=PUT "$S3/$b" 2>&1 && echo "OK: $b" || echo "WARN: $b (may exist)"
done

# List all buckets
echo "==> Current buckets:"
wget -q -O - "$S3/" 2>&1 | grep -o '<Name>[^<]*</Name>' | sed 's/<[^>]*>//g'
