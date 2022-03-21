#!/usr/bin/env python

import click
import csv
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
def reset(driver_path: str, routers: str, dns: str, start_from: int):
    router_data = []
    with open(routers) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=",")
        for row in csv_reader:
            router_data.append(row)

    router_data = router_data[start_from:]

    srv = Service(driver_path)
    op = webdriver.ChromeOptions()

    for r in router_data:
        router_ip, router_username, router_password = r
        dns_servers = dns.split(",")
        router_url = f"http://{router_ip}"

        logger.info(f"Processing {router_ip}")
        driver = webdriver.Chrome(service=srv, options=op)
        try:
            driver.get(router_url)
        except WebDriverException:
            logger.warning(f"Connection to {router_ip} failed, skipping")
            continue

        # Login
        username_field = driver.find_element(By.ID, "Frm_Username")
        password_field = driver.find_element(By.ID, "Frm_Password")
        username_field.send_keys(router_username)
        password_field.send_keys(router_password)

        driver.find_element(By.ID, "LoginId").click()
        logger.info(f"Logged in")

        # Navigate to DNS settings page
        try:
            WebDriverWait(driver, timeout=5).until(lambda d: d.find_element(By.ID, "LANUrl"))
        except TimeoutException:
            logger.warning(f"Timed out waiting for LANUrl element, apparently login failed, skipping ...")
            continue
        driver.find_element(By.ID, "LANUrl").click()

        WebDriverWait(driver, timeout=10).until(lambda d: d.find_element(By.ID, "smDns"))
        driver.find_element(By.ID, "smDns").click()

        WebDriverWait(driver, timeout=10).until(lambda d: d.find_element(By.ID, "LocalDnsServerBar"))
        driver.find_element(By.ID, "LocalDnsServerBar").click()

        # Update DNS settings
        WebDriverWait(driver, timeout=10).until(lambda d: d.find_element(By.ID, "sub_SerIPAddress10"))

        for row in range(1, 3):
            logger.info(f"Updating DNS server #{row}")
            for octet_id in range(4):
                octet_input = driver.find_element(By.ID, f"sub_SerIPAddress{row}{octet_id}")
                octet_input.clear()
                octet_input.send_keys(dns_servers[row - 1].split(".")[octet_id])

        sleep(1)
        driver.find_element(By.ID, "Btn_apply_LocalDnsServer").click()
        logger.info(f"DNS settings were updated")
        sleep(2)
        driver.close()


if __name__ == "__main__":
    cli()
