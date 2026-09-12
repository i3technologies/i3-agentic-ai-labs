#!/bin/bash
curl -sf http://localhost:8080/auth/realms/i3/.well-known/openid-configuration \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print("ISSUER="+d["issuer"])'
