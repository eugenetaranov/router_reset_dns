#!/usr/bin/env python

import click
import csv
import yaml
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, TimeoutException
from loguru import logger
from time import sleep


@click.group()
def cli():
    pass


@cli.command()
@click.option("-d", "--driver-path", type=click.Path(), help="Chromium driver path")
@click.option("-r", "--routers", type=click.Path(), help="CSV file containing router data: ip, username, password")
@click.option("--dns", help="Comma separated list of dns servers: 8.8.8.8,1.1.1.1")
@click.option("--start-from", default=0, help="Start from line N in router-data file")
@click.option("-c", "--config", type=click.Path(), help="Config file, yaml")
def reset(driver_path: str, routers: str, dns: str, start_from: int, config: str):
    router_data = []
    with open(routers) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=",")
        for row in csv_reader:
            router_data.append(row)

    with open(config, "r") as f:
        cfg = yaml.safe_load(f)

    router_data = router_data[start_from:]
    srv = Service(driver_path)
    op = webdriver.ChromeOptions()

    for r in router_data:
        router_ip, router_username, router_password, model = r
        dns_servers = dns.split(",")
        router_url = f"http://{router_ip}"

        logger.info(f"Processing {router_ip}")
        driver = webdriver.Chrome(service=srv, options=op)
        try:
            driver.get(router_url)
        except WebDriverException:
            driver.close()
            logger.warning(f"Connection to {router_ip} failed, skipping")
            continue

        # Login
        if cfg["routers"][model]["login"]["username"]["type"] == "id":
            username_field = driver.find_element(By.ID, cfg["routers"][model]["login"]["username"]["location"])
            username_field.send_keys(router_username)

        if cfg["routers"][model]["login"]["password"]["type"] == "id":
            password_field = driver.find_element(By.ID, cfg["routers"][model]["login"]["password"]["location"])
            password_field.send_keys(router_password)

        if cfg["routers"][model]["login"]["submit"]["type"] == "id":
            driver.find_element(By.ID, cfg["routers"][model]["login"]["submit"]["location"]).click()

        logger.info(f"Logged in")

        # Navigate to DNS settings page
        for step in cfg["routers"][model]["steps"]:
            try:
                if step["type"] == "id":
                    WebDriverWait(driver, timeout=5).until(lambda d: d.find_element(By.ID, step["location"]))
            except TimeoutException:
                driver.close()
                logger.warning(f"Element {step['location']} was not found, skipping router ...")
                continue

            if step["type"] == "id":
                driver.find_element(By.ID, step["location"]).click()

        # Update DNS settings
        logger.info(f"Updating DNS server settings")
        for dns_idx in range(2):
            if cfg["routers"][model]["dns"]["split_octets"]:
                octets = dns_servers[dns_idx].split(".")
                for idx, loc in enumerate(cfg["routers"][model]["dns"][f"dns_{dns_idx+1}"]["location"]):
                    if cfg["routers"][model]["dns"][f"dns_{dns_idx+1}"]["type"] == "id":
                        WebDriverWait(driver, timeout=10).until(lambda d: d.find_element(By.ID, loc))
                        octet_input = driver.find_element(By.ID, loc)
                        octet_input.clear()
                        octet_input.send_keys(octets[idx])

        sleep(1)
        if cfg["routers"][model]["dns"]["submit"]["type"] == "id":
            driver.find_element(By.ID, cfg["routers"][model]["dns"]["submit"]["location"]).click()

        logger.info(f"DNS settings were updated")
        sleep(3)
        driver.close()


if __name__ == "__main__":
    cli()
