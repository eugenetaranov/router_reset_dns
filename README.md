1. Install python3

2. Create virtual env:
```shell
python3 -m venv venv 
source venv/bin/activate
```

3. Install dependencies:
```shell
pip3 install -r requirements.txt
```

4. Install driver for chrome browser from http://chromedriver.chromium.org/downloads

5. Create a csv file with routers data:
```csv
192.168.0.1;80;;;admin:admin;ZTE_ZXHN_H298A
```

6. Add/Update router settings, if needed to config.yaml. It describes steps needed to login, navigate to DNS settings page and update settings.

7. Run:
```shell
./router_reset_dns.py reset --driver-path ~/Downloads/chromedriver_mac64_m1/chromedriver --routers routers.csv --dns 8.8.8.8,1.1.1.1  --config config.yaml

```
Optinally, you can set `--start-from` which effectively skips any preceeding items in the routers file. 
