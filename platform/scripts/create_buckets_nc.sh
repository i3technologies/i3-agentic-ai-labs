#!/bin/sh
# Create SeaweedFS S3 buckets via HTTP PUT from inside the cluster
S3="http://seaweedfs-s3.i3-ott.svc:8333"
BUCKETS="talent-cvs talent-certs talent-reports sit-course-content sit-exam-assets sit-professional-docs sit-credentials ar-context ford-evidence"
for b in $BUCKETS; do
  # SeaweedFS S3 accepts PUT /<bucket> to create
  result=$(nc -z seaweedfs-s3.i3-ott.svc 8333 2>&1 && echo "open" || echo "closed")
  printf "PUT /$b HTTP/1.0\r\nHost: seaweedfs-s3.i3-ott.svc\r\nContent-Length: 0\r\n\r\n" | nc seaweedfs-s3.i3-ott.svc 8333
  echo "done: $b"
done
