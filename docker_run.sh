#!/bin/bash


while getopts r:c:d: flag
do
    case "${flag}" in
        r) routers=${OPTARG};;
        c) config=${OPTARG};;
        d) dns=${OPTARG};;
    esac
done

sudo docker run --rm -ti -v $PWD:/mnt --entrypoint /usr/bin/python3 router_dns_update router_reset_dns.py reset --driver-path /usr/bin/chromedriver --routers ${routers:-routers.csv} --dns ${dns:-8.8.8.8,1.1.1.1} --config ${config:-config.yaml} --start-from 0
