1. Install python3

2. Install dependencies:
```shell
pip3 install selenium
pip3 install click
```

4. Install driver for chrome browser from http://chromedriver.chromium.org/downloads

5. Create a csv file with routers data:
```csv
"95.152.40.204","admin","password"
```

4. Run:
```shell
./reset_dns_zte.py reset --driver-path ~/Downloads/chromedriver_mac64_m1/chromedriver --routers routers.csv --dns 8.8.8.8,1.1.1.1
```
Optinally, you can set `--start-from` which effectively skips any preceeding items in the routers file. 
