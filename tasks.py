from invoke import task

DRIVER_PATH = "~/Downloads/chromedriver_mac64_m1/chromedriver"

@task
def test_password_change(ctx, start_from=0):
    if start_from > 2:
        start_from = start_from - 2

    ctx.run(f"./router_reset_dns.py reset \
  --driver-path {DRIVER_PATH} \
  --routers routers_test_all.csv \
  --new-password 1111 \
  --config config.yaml \
  --start-from {start_from} \
  --debug")
