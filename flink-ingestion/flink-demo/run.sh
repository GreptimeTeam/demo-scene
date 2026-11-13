#!/bin/sh
set -eu

# start the Flink cluster
/opt/flink/bin/start-cluster.sh

# submit the flink-demo job
exec /opt/flink/bin/flink run flink-demo.jar
