FROM docker.io/greptime/grafana-greptimedb:11.2-greptime-v1.1.7

RUN grafana cli plugins install marcusolsson-treemap-panel

ENTRYPOINT [ "/run.sh" ]
