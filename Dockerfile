FROM selenium/standalone-chrome:4.1.3-20220327
ARG DEBIAN_FRONTEND=noninteractive
ARG TINI_VERSION=v0.19.0
ARG DISPLAY=:99
USER root
RUN apt update && apt install -y python3-pip
ADD https://github.com/krallin/tini/releases/download/$TINI_VERSION/tini /tini
RUN chmod +x /tini
RUN chmod +x /tini && \
    pip3 install click pyyaml selenium webdriver-manager loguru
USER seluser
WORKDIR /mnt
ENTRYPOINT ["/tini", "--"]
