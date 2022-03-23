#!/usr/bin/env python

import click
import csv
import yaml
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from loguru import logger
from time import sleep


@click.group()
def cli():
    pass


def map_model(cfg: dict, router_model: str) -> str:
    # logger.info(cfg)
    # logger.info(router_model)
    for model_group in cfg.keys():
        if cfg[model_group]:
            for model in cfg[model_group]:
                if model == router_model:
                    return model_group

    return ""


def waiter(driver: object, find_by: str, loc: str) -> bool:
    """waiter for elements"""
    try:
        if find_by == "id":
            WebDriverWait(driver, timeout=5).until(lambda d: d.find_element(By.ID, loc))
        elif find_by == "xpath":
            WebDriverWait(driver, timeout=5).until(lambda d: d.find_element(By.XPATH, loc))
    except TimeoutException:
        driver.close()
        logger.warning(f"Timed out waiting for {loc} element, apparently login failed, skipping ...")
        return False

    return True


@cli.command()
@click.option("-d", "--driver-path", type=click.Path(), help="Chromium driver path")
@click.option("-r", "--routers", type=click.Path(), help="CSV file containing router data")
@click.option("--dns", help="Comma separated list of dns servers: 8.8.8.8,1.1.1.1")
@click.option("--start-from", default=0, help="Start from line N in router-data file")
@click.option("-c", "--config", type=click.Path(), help="Config file, yaml")
def reset(driver_path: str, routers: str, dns: str, start_from: int, config: str):
    router_data = []
    with open(routers) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=";")
        next(csv_reader)  # skip headers
        for row in csv_reader:
            router_data.append(row)

    with open(config, "r") as f:
        cfg = yaml.safe_load(f)

    router_data = router_data[start_from:]
    srv = Service(driver_path)
    op = webdriver.ChromeOptions()

    for r in router_data:
        router_ip = r[0]
        router_port = r[1]
        try:
            router_username, router_password = r[4].split(":")
        except (ValueError, IndexError):
            logger.warning(f"Unable to parse login/password {r[4]}, skipping ...")
            continue
        model = r[5]
        if router_port == "443":
            router_proto = "https"
        else:
            router_proto = "http"

        group_model = map_model(cfg=cfg["models"], router_model=model)
        if not group_model:
            logger.warning(f"Model {model} for {router_ip} was not found in configured models, skipping ...")
            continue

        dns_servers = dns.split(",")
        router_url = f"{router_proto}://{router_ip}:{router_port}"

        logger.info(f"Processing {router_ip}")
        driver = webdriver.Chrome(service=srv, options=op)
        driver.set_page_load_timeout(20)
        try:
            driver.get(router_url)
        except WebDriverException:
            driver.close()
            logger.warning(f"Connection to {router_ip} failed, skipping")
            continue

        # Login
        if cfg["routers"][group_model]["login"]["username"]["type"] == "id":
            try:
                username_field = driver.find_element(By.ID,
                                                     cfg["routers"][group_model]["login"]["username"]["location"])
            except NoSuchElementException:
                driver.close()
                logger.error(f"Username field was not found, skipping ...")
                continue

            username_field.send_keys(router_username)

        if cfg["routers"][group_model]["login"]["password"]["type"] == "id":
            password_field = driver.find_element(By.ID, cfg["routers"][group_model]["login"]["password"]["location"])
            password_field.send_keys(router_password)

        if cfg["routers"][group_model]["login"]["submit"]["type"] == "id":
            driver.find_element(By.ID, cfg["routers"][group_model]["login"]["submit"]["location"]).click()

        logger.info(f"Logged in")

        # Navigate to DNS settings page
        if "iframe" in cfg["routers"][group_model].keys():
            driver.switch_to.frame(cfg["routers"][group_model]["iframe"])

        for step in cfg["routers"][group_model]["steps"]:
            try:
                if step["type"] == "id":
                    WebDriverWait(driver, timeout=5).until(lambda d: d.find_element(By.ID, step["location"]))
                if step["type"] == "xpath":
                    WebDriverWait(driver, timeout=5).until(lambda d: d.find_element(By.XPATH, step["location"]))
            except TimeoutException:
                driver.close()
                logger.warning(f"Element {step['location']} was not found, skipping router ...")
                continue

            if step["type"] == "id":
                try:
                    driver.find_element(By.ID, step["location"]).click()
                except TimeoutException:
                    driver.close()
                    logger.error(f"Timed out waiting for step {step['location']}, skipping...")
                    continue
            if step["type"] == "xpath":
                try:
                    driver.find_element(By.XPATH, step["location"]).click()
                except TimeoutException:
                    driver.close()
                    logger.error(f"Timed out waiting for step {step['location']}, skipping...")
                    continue
                driver.find_element(By.XPATH, step["location"]).click()

        # Update DNS settings
        logger.info(f"Updating DNS server settings")

        if "iframe" in cfg["routers"][group_model]["dns"].keys():
            driver.switch_to.frame(cfg["routers"][group_model]["dns"]["iframe"])

        for dns_idx in range(2):
            if cfg["routers"][group_model]["dns"]["split_octets"]:
                octets = dns_servers[dns_idx].split(".")
                for idx, loc in enumerate(cfg["routers"][group_model]["dns"][f"dns_{dns_idx + 1}"]["location"]):
                    if cfg["routers"][group_model]["dns"][f"dns_{dns_idx + 1}"]["type"] == "id":
                        w = waiter(driver=driver, find_by="id", loc=loc)
                        if not w:
                            continue
                        octet_input = driver.find_element(By.ID, loc)
                        octet_input.clear()
                        octet_input.send_keys(octets[idx])
            else:
                loc = cfg["routers"][group_model]["dns"][f"dns_{dns_idx + 1}"]["location"]
                if cfg["routers"][group_model]["dns"][f"dns_{dns_idx + 1}"]["type"] == "id":
                    w = waiter(driver=driver, find_by="id", loc=loc)
                    if not w:
                        continue
                    octet_input = driver.find_element(By.ID, loc)
                    octet_input.clear()
                    octet_input.send_keys(dns_servers[dns_idx])
                if cfg["routers"][group_model]["dns"][f"dns_{dns_idx + 1}"]["type"] == "xpath":
                    w = waiter(driver=driver, find_by="xpath", loc=loc)
                    if not w:
                        continue
                    octet_input = driver.find_element(By.XPATH, loc)
                    octet_input.clear()
                    octet_input.send_keys(dns_servers[dns_idx])

        sleep(1)
        if cfg["routers"][group_model]["dns"]["submit"]["type"] == "id":
            w = waiter(driver=driver, find_by="id", loc=cfg["routers"][group_model]["dns"]["submit"]["location"])
            if not w:
                continue
            driver.find_element(By.ID, cfg["routers"][group_model]["dns"]["submit"]["location"]).click()

        if cfg["routers"][group_model]["dns"]["submit"]["type"] == "xpath":
            w = waiter(driver=driver, find_by="xpath", loc=cfg["routers"][group_model]["dns"]["submit"]["location"])
            if not w:
                continue
            driver.find_element(By.XPATH, cfg["routers"][group_model]["dns"]["submit"]["location"]).click()

        logger.info(f"DNS settings were updated")
        sleep(3)
        driver.close()


if __name__ == "__main__":
    cli()
