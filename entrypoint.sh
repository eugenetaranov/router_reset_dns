#!/bin/bash

set -e

echo "Starting Xvfb"
Xvfb &

python3 router_reset_dns.py reset --driver-path /usr/bin/chromedriver --routers routers.csv --dns 8.8.8.8,1.1.1.1 --config config.yaml --start-from 0


