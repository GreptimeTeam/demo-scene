# #! /usr/bin/env bash

set -o errexit
set -o nounset
set -o pipefail

DEPLOY_UTILS_IMAGE=greptime-registry.cn-hangzhou.cr.aliyuncs.com/greptime/deploy-utils:v0.1.0
KIND_NODE_IMAGE=greptime-registry.cn-hangzhou.cr.aliyuncs.com/kindest/node:v1.27.3
DEPLOY_NAMESPACE=default
KIND_CLUSTER_NAME=demo-enterprise-dashboard
WORKING_DIR=enterprise-dashboard

# The default timeout for waiting for resources to be ready.
DEFAULT_TIMEOUT=300s

# Define the color for the output.
RED='\033[1;31m'
GREEN='\033[1;32m'
BLUE='\033[1;34m'
RESET='\033[0m'

function check_prerequisites() {
  echo "${GREEN}=> Check prerequisites...${RESET}"

  if ! hash docker 2>/dev/null; then
    echo "${RED}docker command is not found! You can download docker here: https://docs.docker.com/get-docker/${RESET}"
    exit
  fi

  if ! hash kind 2>/dev/null; then
    echo "${RED}kind command is not found! You can download kind here: https://kind.sigs.k8s.io/docs/user/quick-start/#installing-from-release-binaries${RESET}"
    exit
  fi

  echo "${GREEN}<= All prerequisites are met.${RESET}"
}

function create_kind_cluster() {
  # If the cluster already exists, skip the creation
  if kind get clusters | grep -q ${KIND_CLUSTER_NAME}; then
    echo "${BLUE}kind cluster '${KIND_CLUSTER_NAME}' already exists. Skipping creation.${RESET}"
    return
  fi

  kind create cluster --name ${KIND_CLUSTER_NAME} --kubeconfig ./kubeconfig-${KIND_CLUSTER_NAME}.yaml --image ${KIND_NODE_IMAGE}
}

function deploy_greptimedb_operator() {
  echo "${GREEN}=> Deploy greptimedb-operator...${RESET}"

  docker run --rm \
    --network host \
    -v $(pwd):/${WORKING_DIR} \
    -w /${WORKING_DIR} \
    "${DEPLOY_UTILS_IMAGE}" \
    helm upgrade \
      --install greptimedb-operator \
      oci://greptime-registry.cn-hangzhou.cr.aliyuncs.com/charts/greptimedb-operator \
      --values /${WORKING_DIR}/values/greptimedb-operator/values.yaml \
      --namespace ${DEPLOY_NAMESPACE} \
      --kubeconfig /${WORKING_DIR}/kubeconfig-${KIND_CLUSTER_NAME}.yaml

  echo "${GREEN}<= greptimedb-operator is deployed.${RESET}"
}

function deploy_etcd_cluster() {
  echo "${GREEN}=> Deploy etcd cluster...${RESET}"
  docker run --rm \
    --network host \
    -v $(pwd):/${WORKING_DIR} \
    -w /${WORKING_DIR} \
    "${DEPLOY_UTILS_IMAGE}" \
    helm upgrade \
      --install etcd \
      oci://greptime-registry.cn-hangzhou.cr.aliyuncs.com/charts/etcd \
      --values /${WORKING_DIR}/values/etcd-cluster/values.yaml \
      --namespace ${DEPLOY_NAMESPACE} \
      --kubeconfig /${WORKING_DIR}/kubeconfig-${KIND_CLUSTER_NAME}.yaml

  echo "${GREEN}<= etcd cluster is deployed.${RESET}"
}

function deploy_metrics_server() {
  echo "${GREEN}=> Deploy metrics-server...${RESET}"

  docker run --rm \
    --network host \
    -v $(pwd):/${WORKING_DIR} \
    -w /${WORKING_DIR} \
    "${DEPLOY_UTILS_IMAGE}" \
    kubectl --kubeconfig /${WORKING_DIR}/kubeconfig-${KIND_CLUSTER_NAME}.yaml \
      apply -f /${WORKING_DIR}/manifests/metrics-server/metrics-server.yaml

  echo "${GREEN}<= metrics-server is deployed.${RESET}"
}

function deploy_greptimedb_cluster() {
  echo "${GREEN}=> Deploy greptimedb cluster...${RESET}"

  docker run --rm \
    --network host \
    -v $(pwd):/${WORKING_DIR} \
    -w /${WORKING_DIR} \
    "${DEPLOY_UTILS_IMAGE}" \
    helm upgrade \
      --install mycluster \
      oci://greptime-registry.cn-hangzhou.cr.aliyuncs.com/charts/greptimedb-cluster \
      --values /${WORKING_DIR}/values/greptimedb-cluster/values.yaml \
      --namespace ${DEPLOY_NAMESPACE} \
      --kubeconfig /${WORKING_DIR}/kubeconfig-${KIND_CLUSTER_NAME}.yaml
  
  echo "${GREEN}=> Wait for greptimedb-cluster to be ready...${RESET}"
  
  # Wait for greptimedb-cluster to be ready.
  wait_for \
    "docker run --network host --rm -v $(pwd):/${WORKING_DIR} -w /${WORKING_DIR} ${DEPLOY_UTILS_IMAGE} kubectl --kubeconfig /${WORKING_DIR}/kubeconfig-${KIND_CLUSTER_NAME}.yaml -n ${DEPLOY_NAMESPACE} get gtc mycluster -o json | jq '.status.clusterPhase' | grep Running" \
    "${DEFAULT_TIMEOUT%s}"

  echo "${GREEN}<= greptimedb cluster is ready.${RESET}"
}

function wait_dependencies_ready() {
  echo "${GREEN}=> Wait for dependencies to be ready...${RESET}"

  # Sleep for 5 seconds to make sure the dependencies are deployed.
  sleep 5

  # Wait for etcd to be ready.
  docker run --rm \
    --network host \
    -v $(pwd):/${WORKING_DIR} \
    -w /${WORKING_DIR} \
    "${DEPLOY_UTILS_IMAGE}" \
    kubectl wait \
      --kubeconfig /${WORKING_DIR}/kubeconfig-${KIND_CLUSTER_NAME}.yaml \
      --for=condition=Ready \
      pod -l app.kubernetes.io/instance=etcd \
      -n ${DEPLOY_NAMESPACE} \
      --timeout="$DEFAULT_TIMEOUT"

  # Wait for greptimedb-operator to be ready.
  docker run --rm \
    --network host \
    -v $(pwd):/${WORKING_DIR} \
    -w /${WORKING_DIR} \
    "${DEPLOY_UTILS_IMAGE}" \
    kubectl rollout \
      --kubeconfig /${WORKING_DIR}/kubeconfig-${KIND_CLUSTER_NAME}.yaml \
      status deployment/greptimedb-operator \
      -n ${DEPLOY_NAMESPACE} \
      --timeout="$DEFAULT_TIMEOUT"
  
  echo "${GREEN}<= All services are ready.${RESET}"
}

function deploy_enterprise_dashboard() {
  echo "${GREEN}=> Deploy enterprise-dashboard...${RESET}"
  docker run --rm \
    --network host \
    -v $(pwd):/${WORKING_DIR} \
    -w /${WORKING_DIR} \
    "${DEPLOY_UTILS_IMAGE}" \
    helm upgrade \
      --install enterprise-dashboard \
      oci://greptime-registry.cn-hangzhou.cr.aliyuncs.com/charts/enterprise-dashboard \
      --values /${WORKING_DIR}/values/enterprise-dashboard/values.yaml \
      --namespace ${DEPLOY_NAMESPACE} \
      --kubeconfig /${WORKING_DIR}/kubeconfig-${KIND_CLUSTER_NAME}.yaml

  # Wait for enterprise-dashboard to be ready.
  docker run --rm \
    --network host \
    -v $(pwd):/${WORKING_DIR} \
    -w /${WORKING_DIR} \
    "${DEPLOY_UTILS_IMAGE}" \
    kubectl rollout \
      --kubeconfig /${WORKING_DIR}/kubeconfig-${KIND_CLUSTER_NAME}.yaml \
      status deployment/enterprise-dashboard \
      -n ${DEPLOY_NAMESPACE} \
      --timeout="$DEFAULT_TIMEOUT"

  echo "${GREEN}<= enterprise-dashboard is deployed.${RESET}"
}

function port_forward_enterprise_dashboard() {
  echo "${GREEN}=> Port forward enterprise-dashboard...${RESET}"
  docker run --rm \
    --network host \
    -v $(pwd):/${WORKING_DIR} \
    -w /${WORKING_DIR} \
    "${DEPLOY_UTILS_IMAGE}" \
    kubectl port-forward \
      --kubeconfig /${WORKING_DIR}/kubeconfig-${KIND_CLUSTER_NAME}.yaml \
      svc/enterprise-dashboard 19095:19095 -n ${DEPLOY_NAMESPACE}
}

function wait_for() {
  local command="$1"
  local timeout="$2"
  local interval=1
  local elapsed_time=0

  while true; do
    # Turn off the exit-on-error flag to avoid exiting the script.
    set +e
    eval "$command" &> /dev/null
    local status=$?
    set -e

    # Check if command was successful.
    if [[ $status -eq 0 ]]; then
      return 0
    fi

    # Update elapsed time.
    ((elapsed_time += interval))

    # Check if the timeout has been reached.
    if [[ $elapsed_time -ge $timeout ]]; then
      echo "Timeout reached. Command failed."
      return 1
    fi

    # Wait for a specified interval before retrying.
    sleep $interval
  done
}

function main() {
  check_prerequisites
  create_kind_cluster
  deploy_greptimedb_operator
  deploy_etcd_cluster
  deploy_metrics_server
  wait_dependencies_ready
  deploy_greptimedb_cluster
  deploy_enterprise_dashboard
  port_forward_enterprise_dashboard
}

main
