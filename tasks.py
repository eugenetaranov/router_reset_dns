from invoke import task

DRIVER_PATH = "~/Downloads/chromedriver_mac64_m1/chromedriver"
NEW_PASSWORD = "1112"

@task
def test_password_change(ctx, start_from=0):
    if start_from > 2:
        start_from = start_from - 2

    cmd = f"./router_reset_dns.py reset \
  --driver-path {DRIVER_PATH} \
  --routers routers_test_all.csv \
  --new-password {NEW_PASSWORD} \
  --config config.yaml \
  --start-from {start_from} \
  --debug"

    print(cmd)
    ctx.run(cmd)
