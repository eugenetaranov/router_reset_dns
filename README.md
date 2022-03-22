1. Install python3

2. Install dependencies:
```shell
pip3 install selenium
pip3 install click
```

3. Install driver for chrome browser from http://chromedriver.chromium.org/downloads

4. Create a csv file with routers data:
```csv
192.168.0.1,admin,password,ZTE_F612
```

5. Add/Update router settings, if needed to config.yaml. It describes steps needed to login, navigate to DNS settings page and update settings.

7. Run:
```shell
./router_reset_dns.py reset --driver-path ~/Downloads/chromedriver_mac64_m1/chromedriver --routers routers.csv --dns 8.8.8.8,1.1.1.1  --config config.yaml

```
Optinally, you can set `--start-from` which effectively skips any preceeding items in the routers file. 
