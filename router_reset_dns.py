#!/usr/bin/env python
import sys
from typing import Optional
import click
import csv
import yaml
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from loguru import logger
from time import sleep
import subprocess
import signal


@click.group()
def cli():
    pass


def preexec_function():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def map_model(cfg: dict, router_model: str) -> str:
    # logger.info(cfg)
    # logger.info(router_model)
    for model_group in cfg.keys():
        if cfg[model_group]:
            for model in cfg[model_group]:
                if model == router_model:
                    return model_group

    return ""


class Element():
    def __init__(self, driver: webdriver, element: dict):
        self.driver = driver
        self.kind = element["type"]
        self.loc = element["location"]

    def _wait(self):
        """waiter for elements"""
        timeout = 60

        logger.debug(f"Waiting for {self.kind} {self.loc}")
        try:
            if self.kind == "id":
                WebDriverWait(self.driver, timeout=timeout).until(EC.element_to_be_clickable((By.ID, self.loc)))

            elif self.kind == "xpath":
                WebDriverWait(self.driver, timeout=timeout).until(
                    EC.element_to_be_clickable((By.XPATH, self.loc)))

            else:
                raise NotImplementedError

        except TimeoutException:
            logger.warning(f"Timed out waiting for {self.loc} element, apparently login failed, skipping ...")
            raise

    def click(self):
        self._wait()

        if self.kind == "id":
            self.driver.find_element(By.ID, self.loc).click()

        elif self.kind == "xpath":
            self.driver.find_element(By.XPATH, self.loc).click()

        else:
            raise NotImplementedError

    def input(self, input_value: str, click_alert: bool = False):
        w = self._wait()

        if click_alert:
            self.click()
            WebDriverWait(self.driver, timeout=10).until(EC.alert_is_present())
            self.driver.switch_to.alert.accept()

        if self.kind == "id":
            input_element = self.driver.find_element(By.ID, self.loc)

        elif self.kind == "xpath":
            input_element = self.driver.find_element(By.XPATH, self.loc)

        else:
            raise NotImplementedError

        input_element.clear()
        input_element.send_keys(input_value)


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
        if "basic" in self.cfg["login"] and self.cfg["login"]["basic"]:
            self.router_url = f"{self.router_proto}://{self.router_user}:{self.router_password}@{self.router_ip}:{self.router_port}"
        else:
            self.router_url = f"{self.router_proto}://{self.router_ip}:{self.router_port}"
        self.driver = webdriver.Chrome(service=driver_srv, options=driver_options)
        # self.driver.set_page_load_timeout(60)

    def __del__(self):
        try:
            self.driver.close()
        except:
            pass

    def _waiter(self, element: dict) -> bool:
        """waiter for elements"""
        timeout = 60
        type = element["type"]
        loc = element["location"]
        logger.debug(f"Waiting for {type} {loc}")
        try:
            if type == "id":
                WebDriverWait(self.driver, timeout=timeout).until(lambda d: d.find_element(By.ID, loc))
            elif type == "xpath":
                WebDriverWait(self.driver, timeout=timeout).until(lambda d: d.find_element(By.XPATH, loc))
            else:
                logger.error(f"Not implemented")
                return False
        except TimeoutException:
            logger.warning(f"Timed out waiting for {loc} element, apparently login failed, skipping ...")
            return False

        return True

    def reset_dns(self) -> bool:
        res = self.open_main_page()
        if not res:
            return False

        if not "basic" in self.cfg["login"]:
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

    def open_main_page(self) -> bool:
        try:
            self.driver.get(self.router_url)
        except WebDriverException:
            self.driver.close()
            logger.warning(f"Connection to {self.router_ip} failed, skipping...")
            return False

        return True

    # login wrapper
    def do_login(self) -> bool:
        res = False
        # both username and password are present
        if "username" in self.cfg["login"] and "password" in self.cfg["login"]:
            res = self._do_login_with_login_and_password()

        # only password is present
        if not "username" in self.cfg["login"] and "password" in self.cfg["login"]:
            res = self._do_login_with_password_only()

        return res

    # password only login
    def _do_login_with_password_only(self) -> bool:
        w = self._waiter(element=self.cfg["login"]["password"])
        if not w:
            logger.warning(
                f"Timed out waiting for {self.cfg['login']['password']['location']}, skipping...")
            return False

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

        return True

    # common login with username and password
    def _do_login_with_login_and_password(self) -> bool:

        logger.info(f"Username: {self.router_user}")
        logger.info(f"Password: {self.router_password}")

        username_input = Element(driver=self.driver, element=self.cfg["login"]["username"])
        username_input.input(input_value=self.router_user)

        password_input = Element(driver=self.driver, element=self.cfg["login"]["password"])
        password_input.input(input_value=self.router_password)

        login_button = Element(driver=self.driver, element=self.cfg["login"]["submit"])
        login_button.click()

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
            logger.debug(f"Switched to frame {self.cfg['iframe']}")

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
                if "value" in step.keys():
                    try:
                        value_mode = self.driver.find_element(By.ID, step["location"])
                        value_mode = Select(value_mode)
                        value_mode.select_by_value(str(step["value"]))
                    except TimeoutException:
                        logger.error(f"Timed out waiting for step {step['location']}, skipping...")

            if step["type"] == "frame":
                try:
                    self.driver.switch_to.parent_frame()
                    #                    fr = self.driver.findElementById(step["location"])
                    self.driver.switch_to.frame(step["location"])
                    logger.debug(f"Switched to frame {step['location']}")
                except NameError:
                    logger.error(f"Can't switch to frame:  {step['location']}, skipping...{(NameError)}")
                    return False
            elif step["type"] == "xpath":
                try:
                    self.driver.find_element(By.XPATH, step["location"]).click()
                except TimeoutException:
                    logger.error(f"Timed out waiting for step {step['location']}, skipping...")
                    return False

        if "switch_to_parent_frame" in self.cfg.keys() and self.cfg["switch_to_parent_frame"]:
            self.driver.switch_to.parent_frame()
            logger.debug(f"Switched to parent frame")

        return True

    def open_password_change_page(self):
        if "iframe" in self.cfg["password_reset"]["goto"]:
            self.driver.switch_to.frame(frame_reference=self.cfg["password_reset"]["goto"]["iframe"])

        for step in self.cfg["password_reset"]["goto"]["steps"]:
            logger.debug(f"Step {step}")

            el = Element(driver=self.driver, element=step)
            el.click()
            logger.info(f"Step {step} passed")

        if "iframe" in self.cfg["password_reset"]["goto"]:
            self.driver.switch_to.parent_frame()

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
                logger.info("Updating DHCP mode")
                dhcp_mode = Select(dhcp_mode)
                try:
                    dhcp_mode.select_by_value(str(self.cfg["dns"]["update_dhcp_mode"]["value"]))
                except NoSuchElementException as e:
                    logger.error(e)
                    return False

        return True

    def update_dns_settings(self) -> bool:
        logger.info(f"Updating DNS server settings")

        if "iframe" in self.cfg["dns"].keys():
            self.driver.switch_to.frame(self.cfg["dns"]["iframe"])

        res = self.set_dhcp_mode()
        if not res:
            return False

        dns_fields_num = len([k for k in self.cfg["dns"].keys() if k.startswith("dns_")])
        for dns_idx in range(dns_fields_num):
            if self.cfg["dns"]["split_octets"]:
                octets = self.dns_servers[dns_idx].split(".")

                for idx, loc in enumerate(self.cfg["dns"][f"dns_{dns_idx + 1}"]["location"]):
                    if self.cfg["dns"][f"dns_{dns_idx + 1}"]["type"] == "id":
                        try:
                            octet_input = self.driver.find_element(By.ID, loc)
                        except NoSuchElementException:
                            logger.error(f"Element {loc} was not found, skipping...")
                            return False
                        octet_input.clear()
                        octet_input.send_keys(octets[idx])

                    elif self.cfg["dns"][f"dns_{dns_idx + 1}"]["type"] == "xpath":
                        try:
                            octet_input = self.driver.find_element(By.XPATH, loc)
                        except NoSuchElementException:
                            logger.error(f"Element {loc} was not found, skipping...")
                            return False
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

        w = self._waiter(element=self.cfg["dns"]["submit"])
        if not w:
            return False

        Element(driver=self.driver, element=self.cfg["dns"]["submit"]).click()
        logger.info("DNS settings were updated")

        if "wait" in self.cfg["dns"]["submit"]:
            logger.info(f"Waiting {self.cfg['dns']['submit']['wait']} seconds")
            sleep(self.cfg["dns"]["submit"]["wait"])
        else:
            sleep(5)

        return True

    def reset_password(self, password: str) -> bool:
        logger.info(f"Resetting password")
        res = self.open_main_page()
        if not res:
            return False

        if not "basic" in self.cfg["login"]:
            res = self.do_login()

            if not res:
                return False

        self.open_password_change_page()

        if "iframe" in self.cfg["password_reset"]["form"]:
            self.driver.switch_to.frame(frame_reference=self.cfg["password_reset"]["form"]["iframe"])

        if "current_username" in self.cfg["password_reset"]["form"]["input"]:
            Element(self.driver, element=self.cfg["password_reset"]["form"]["input"]["current_username"]).input(input_value=self.router_user)

        if "current_password" in self.cfg["password_reset"]["form"]["input"]:
            Element(self.driver, element=self.cfg["password_reset"]["form"]["input"]["current_password"]).input(input_value=self.router_password)

        if "new_username" in self.cfg["password_reset"]["form"]["input"]:
            Element(self.driver, element=self.cfg["password_reset"]["form"]["input"]["new_username"]).input(input_value=self.router_user)

        if "new_password" in self.cfg["password_reset"]["form"]["input"]:
            Element(self.driver, element=self.cfg["password_reset"]["form"]["input"]["new_password"]).input(input_value=password)

        if "new_password_confirm" in self.cfg["password_reset"]["form"]["input"]:
            Element(self.driver, element=self.cfg["password_reset"]["form"]["input"]["new_password_confirm"]).input(input_value=password)

        submit_btn = Element(driver=self.driver, element=self.cfg["password_reset"]["form"]["submit"])
        submit_btn.click()

        if "iframe" in self.cfg["password_reset"]["form"]:
            self.driver.switch_to.parent_frame()

        # ack popup
        if "alert_confirm" in self.cfg["password_reset"]["form"] and self.cfg["password_reset"]["form"][
            "alert_confirm"]:
            WebDriverWait(self.driver, timeout=10).until(EC.alert_is_present())
            self.driver.switch_to.alert.accept()

        logger.info(f"Password has been updated")

        # optionally reboot
        if "reboot" in self.cfg["password_reset"]:
            logger.info("Rebooting")

            for step in self.cfg["password_reset"]["reboot"]["steps"]:
                Element(driver=self.driver, element=step).click()

            if "alert_confirm" in self.cfg["password_reset"]["reboot"]:
                WebDriverWait(self.driver, timeout=10).until(EC.alert_is_present())
                self.driver.switch_to.alert.accept()

            sleep(5)

        return True


@cli.command()
@click.option("-d", "--driver-path", type=click.Path(), help="Chromium driver path")
@click.option("-r", "--routers", type=click.Path(), help="CSV file containing router data")
@click.option("--dns", help="Comma separated list of dns servers: 8.8.8.8,1.1.1.1")
@click.option("--start-from", default=0, help="Start from line N in router-data file")
@click.option("-c", "--config", type=click.Path(), help="Config file, yaml")
@click.option("--skip-header/--no-skip-header", default=True)
@click.option("--debug/--no-debug", default=False)
@click.option("--docker-runtime/--no-docker-runtime", default=False)
@click.option("--new-password", help="Password will be updated, if specified")
def reset(driver_path: str, routers: str, dns: str, start_from: int, config: str, skip_header: bool, debug: bool,
          docker_runtime: bool, new_password: str):
    if docker_runtime:
        subprocess.Popen(["Xvfb"],
                         stdout=open("/dev/null", "w"),
                         stderr=open("/dev/null", "w"),
                         preexec_fn=preexec_function
                         )

    routers_data = []
    with open(routers, mode="r", encoding="utf8", errors="ignore") as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=";")
        if skip_header:
            next(csv_reader)  # skip header
        for row in csv_reader:
            routers_data.append(row)

    with open(config, "r") as f:
        cfg = yaml.safe_load(f)

    routers_data = routers_data[start_from:]
    if debug:
        routers_data = routers_data[:1]

    srv = Service(driver_path)
    op = webdriver.ChromeOptions()

    op.add_argument("--disable-notifications")
    op.add_argument("--disable-popup-blocking")

    if docker_runtime:
        op.add_argument("--headless")
        op.add_argument("--no-sandbox")
        op.add_argument("--disable-dev-shm-usage")

    for idx, router_data in enumerate(routers_data):
        logger.info(f"Started {idx} router {router_data[0]} {router_data[5]}")
        model = router_data[5]
        group_model = map_model(cfg=cfg["models"], router_model=model)
        if not group_model:
            logger.warning(f"Model {model} for {router_data[0]} was not found in configured models, skipping ...")
            continue

        if ":" in router_data[4]:
            router_user, router_password = router_data[4].split(":")
        else:
            router_user = ""
            router_password = router_data[4]

        if dns:
            if "," in dns:
                dns_servers = dns.split(",")
            else:
                dns_servers = dns
        else:
            dns_servers = []
        router = Router(
            cfg=cfg["routers"][group_model],
            router_ip=router_data[0],
            router_port=router_data[1],
            router_user=router_user,
            router_password=router_password,
            dns_servers=dns_servers,
            driver_srv=srv,
            driver_options=op,
        )

        if dns_servers:
            try:
                router.reset_dns()
            except Exception:
                logger.exception("Failed to reset dns")
                pass

        if new_password:
            try:
                router.reset_password(password=new_password)
            except Exception:
                logger.exception("Failed to reset password")
                pass

        del router


if __name__ == "__main__":
    cli()
