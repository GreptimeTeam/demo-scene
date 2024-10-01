FROM docker.io/grafana/grafana:11.2.0

RUN grafana cli --pluginUrl https://github.com/GreptimeTeam/greptimedb-grafana-datasource/releases/latest/download/info8fcc-greptimedb-datasource.zip plugins install info8fcc

RUN grafana cli plugins install marcusolsson-treemap-panel

ENTRYPOINT [ "/run.sh" ]
