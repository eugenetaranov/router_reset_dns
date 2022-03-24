#!/usr/bin/env python
from typing import Optional

import click
import csv
import yaml
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
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


class Router:
    def __init__(self,
                 cfg: dict,
                 router_ip: str,
                 router_port: str,
                 router_user: str,
                 router_password: str,
                 dns_servers: list,
                 driver_srv: Optional[Service],
                 driver_options: Optional[Options],
                 ) -> None:
        self.cfg = cfg
        self.router_ip = router_ip
        self.router_port = router_port
        self.router_user = router_user
        self.router_password = router_password
        self.dns_servers = dns_servers
        if self.router_port == "443":
            self.router_proto = "https"
        else:
            self.router_proto = "http"
        self.router_url = f"{self.router_proto}://{self.router_ip}:{self.router_port}"
        self.driver = webdriver.Chrome(service=driver_srv, options=driver_options)
        self.driver.set_page_load_timeout(60)

    def __del__(self):
        self.driver.close()

    def _waiter(self, element: dict) -> bool:
        """waiter for elements"""
        type = element["type"]
        loc = element["location"]
        try:
            if type == "id":
                WebDriverWait(self.driver, timeout=30).until(lambda d: d.find_element(By.ID, loc))
            elif type == "xpath":
                WebDriverWait(self.driver, timeout=30).until(lambda d: d.find_element(By.XPATH, loc))
        except TimeoutException:
            logger.warning(f"Timed out waiting for {loc} element, apparently login failed, skipping ...")
            return False

        return True

    def process(self) -> bool:
        res = self.do_login()
        if not res:
            return False

        res = self.open_dns_page()
        if not res:
            return False

        res = self.update_dns_settings()
        if not res:
            return False

        return True

    def do_login(self) -> bool:
        try:
            self.driver.get(self.router_url)
        except WebDriverException:
            self.driver.close()
            logger.warning(f"Connection to {self.router_ip} failed, skipping...")
            return False

        w = self._waiter(element=self.cfg["login"]["username"])
        if not w:
            logger.warning(
                f"Timed out waiting for {self.cfg['login']['username']['location']}, skipping...")
            return False

        if self.cfg["login"]["username"]["type"] == "id":
            try:
                username_field = self.driver.find_element(By.ID,
                                                          self.cfg["login"]["username"]["location"])
            except NoSuchElementException:
                logger.error(f"Username field was not found, skipping ...")
                return False

            username_field.send_keys(self.router_user)

        elif self.cfg["login"]["username"]["type"] == "xpath":
            try:
                username_field = self.driver.find_element(By.XPATH,
                                                          self.cfg["login"]["username"]["location"])
            except NoSuchElementException:
                logger.error(f"Username field was not found, skipping ...")
                return False

            username_field.send_keys(self.router_user)

        if self.cfg["login"]["password"]["type"] == "id":
            password_field = self.driver.find_element(By.ID, self.cfg["login"]["password"]["location"])
            password_field.send_keys(self.router_password)

        elif self.cfg["login"]["password"]["type"] == "xpath":
            password_field = self.driver.find_element(By.XPATH, self.cfg["login"]["password"]["location"])
            password_field.send_keys(self.router_password)

        if self.cfg["login"]["submit"]["type"] == "id":
            self.driver.find_element(By.ID, self.cfg["login"]["submit"]["location"]).click()

        elif self.cfg["login"]["submit"]["type"] == "xpath":
            self.driver.find_element(By.XPATH, self.cfg["login"]["submit"]["location"]).click()

        sleep(2)
        # check if login was successful
        if "check_login" in self.cfg["login"]:
            if "iframe" in self.cfg["login"]["check_login"].keys():
                self.driver.switch_to.frame(self.cfg["login"]["check_login"]["iframe"])

            w = self._waiter(element=self.cfg["login"]["check_login"])
            if not w:
                logger.error(f"Login failed, skipping...")
                return False

            if "iframe" in self.cfg["login"].keys():
                self.driver.switch_to.parent_frame()

        logger.info(f"Logged in")
        return True

    def open_dns_page(self) -> bool:
        if "iframe" in self.cfg.keys():
            self.driver.switch_to.frame(self.cfg["iframe"])

        for step in self.cfg["steps"]:
            w = self._waiter(element=step)
            if not w:
                logger.error(f"Element {step['location']} was not found, skipping router...")
                return False

            if step["type"] == "id":
                try:
                    self.driver.find_element(By.ID, step["location"]).click()
                except TimeoutException:
                    logger.error(f"Timed out waiting for step {step['location']}, skipping...")
                    return False

            elif step["type"] == "xpath":
                try:
                    self.driver.find_element(By.XPATH, step["location"]).click()
                except TimeoutException:
                    logger.error(f"Timed out waiting for step {step['location']}, skipping...")
                    return False
        return True

    def set_dhcp_mode(self):
        if "check_dhcp_mode" in self.cfg["dns"]:
            w = self._waiter(element=self.cfg["dns"]["check_dhcp_mode"])
            if not w:
                return False

            if self.cfg["dns"]["check_dhcp_mode"]["type"] == "id":
                dhcp_mode = self.driver.find_element(By.ID, self.cfg["dns"]["check_dhcp_mode"]["location"])

            elif self.cfg["dns"]["check_dhcp_mode"]["type"] == "xpath":
                dhcp_mode = self.driver.find_element(By.XPATH, self.cfg["dns"]["check_dhcp_mode"]["location"])

            if dhcp_mode.get_attribute("value") != self.cfg["dns"]["update_dhcp_mode"]["value"]:
                dhcp_mode = Select(dhcp_mode)
                dhcp_mode.select_by_visible_text(self.cfg["dns"]["update_dhcp_mode"]["value"])

    def update_dns_settings(self) -> bool:
        logger.info(f"Updating DNS server settings")

        if "iframe" in self.cfg["dns"].keys():
            self.driver.switch_to.frame(self.cfg["dns"]["iframe"])

        self.set_dhcp_mode()

        for dns_idx in range(2):
            if self.cfg["dns"]["split_octets"]:
                octets = self.dns_servers[dns_idx].split(".")

                for idx, loc in enumerate(self.cfg["dns"][f"dns_{dns_idx + 1}"]["location"]):
                    w = self._waiter(element=self.cfg["dns"][f"dns_{dns_idx + 1}"])
                    if not w:
                        return False

                    if self.cfg["dns"][f"dns_{dns_idx + 1}"]["type"] == "id":
                        octet_input = self.driver.find_element(By.ID, loc)
                        octet_input.clear()
                        octet_input.send_keys(octets[idx])

                    elif self.cfg["dns"][f"dns_{dns_idx + 1}"]["type"] == "xpath":
                        octet_input = self.driver.find_element(By.XPATH, loc)
                        octet_input.clear()
                        octet_input.send_keys(octets[idx])

            else:
                loc = self.cfg["dns"][f"dns_{dns_idx + 1}"]["location"]
                w = self._waiter(element=self.cfg["dns"][f"dns_{dns_idx + 1}"])
                if not w:
                    return False

                if self.cfg["dns"][f"dns_{dns_idx + 1}"]["type"] == "id":
                    octet_input = self.driver.find_element(By.ID, loc)
                    octet_input.clear()
                    octet_input.send_keys(self.dns_servers[dns_idx])

                elif self.cfg["dns"][f"dns_{dns_idx + 1}"]["type"] == "xpath":
                    octet_input = self.driver.find_element(By.XPATH, loc)
                    octet_input.clear()
                    octet_input.send_keys(self.dns_servers[dns_idx])

        sleep(1)
        w = self._waiter(element=self.cfg["dns"]["submit"])
        if not w:
            return False

        if self.cfg["dns"]["submit"]["type"] == "id":
            self.driver.find_element(By.ID, self.cfg["dns"]["submit"]["location"]).click()

        elif self.cfg["dns"]["submit"]["type"] == "xpath":
            self.driver.find_element(By.XPATH, self.cfg["dns"]["submit"]["location"]).click()

        logger.info(f"DNS settings were updated")
        sleep(3)
        return True


@cli.command()
@click.option("-d", "--driver-path", type=click.Path(), help="Chromium driver path")
@click.option("-r", "--routers", type=click.Path(), help="CSV file containing router data")
@click.option("--dns", help="Comma separated list of dns servers: 8.8.8.8,1.1.1.1")
@click.option("--start-from", default=0, help="Start from line N in router-data file")
@click.option("-c", "--config", type=click.Path(), help="Config file, yaml")
@click.option("--skip-header/--no-skip-header", default=True)
def reset(driver_path: str, routers: str, dns: str, start_from: int, config: str, skip_header: bool):
    routers_data = []
    with open(routers) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=";")
        if skip_header:
            next(csv_reader)  # skip header
        for row in csv_reader:
            routers_data.append(row)

    with open(config, "r") as f:
        cfg = yaml.safe_load(f)

    routers_data = routers_data[start_from:]
    srv = Service(driver_path)
    op = webdriver.ChromeOptions()

    for router_data in routers_data:
        model = router_data[5]
        group_model = map_model(cfg=cfg["models"], router_model=model)
        if not group_model:
            logger.warning(f"Model {model} for {router_data[0]} was not found in configured models, skipping ...")
            continue
        try:
            router_user, router_password = router_data[4].split(":")
        except (ValueError, IndexError):
            logger.warning(f"Unable to parse login/password {router_data[4]}, skipping ...")
            continue

        router = Router(
            cfg=cfg["routers"][group_model],
            router_ip=router_data[0],
            router_port=router_data[1],
            router_user=router_user,
            router_password=router_password,
            dns_servers=dns.split(","),
            driver_srv=srv,
            driver_options=op,
        )
        router.process()
        del router


if __name__ == "__main__":
    cli()
