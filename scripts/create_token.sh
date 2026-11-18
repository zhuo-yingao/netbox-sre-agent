#!/bin/bash
# Print a NetBox 4.7 v2 token. Put the Bearer line into NETBOX_TOKEN.
dir="${NETBOX_DIR:-/opt/netbox-docker}"
cd "$dir"
docker compose exec -T netbox /opt/netbox/netbox/manage.py shell -c 'from users.models import User, Token
u = User.objects.get(username="admin")
t = Token(user=u, write_enabled=False, description="sre-agent")
t.save()
print(t.get_auth_header_prefix() + t.token)
' | awk '/^Bearer / { print }'
