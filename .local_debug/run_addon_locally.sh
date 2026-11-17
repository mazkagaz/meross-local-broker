#!/bin/bash
# In order to run on the host-network, add the "--network host" parameter
docker run --rm \
    --privileged \
    -p 2001:2001/tcp \
    -p 2003:2003/tcp \
    --env expose_admin_api=true \
    --env advertise=false \
    --env debug_mode=true \
    --mount type=bind,source="$(pwd)"/meross_local_broker/rootfs/opt/custom_broker,target=/opt/custom_broker \
    -v "$(pwd)/.local_debug/data":/data local/meross_local_broker
