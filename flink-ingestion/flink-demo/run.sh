#!/bin/bash

# start the Flink cluster
/opt/flink/bin/start-cluster.sh

# submit the flink-demo job
/opt/flink/bin/flink run flink-demo.jar
