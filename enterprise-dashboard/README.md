# Enterprise Dashboard

Enterprise Dashboard is a enterprise-grade dashboard for manage GreptimeDB resources.

## How to Run

1. Make sure you have installed Docker and [`kind`](https://kind.sigs.k8s.io/docs/user/quick-start/).
2. Execute `./run-enterprise-dashboard.sh` to start the enterprise dashboard;
3. Access the enterprise dashboard at `http://localhost:19095`;

## Clean up

Execute the following command to clean up the resources:

```bash
kind delete cluster --name demo-enterprise-dashboard && rm -rf kubeconfig-demo-enterprise-dashboard.yaml
```
