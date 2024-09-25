FROM docker.io/grafana/grafana:11.1.0

RUN grafana cli --pluginUrl https://github.com/GreptimeTeam/greptimedb-grafana-datasource/releases/latest/download/info8fcc-greptimedb-datasource.zip plugins install info8fcc

ENTRYPOINT [ "/run.sh" ]