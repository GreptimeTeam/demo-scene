FROM ubuntu:22.04

RUN apt-get update && apt-get install -y curl jq yq

# Install Helm.
RUN curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 && \
    chmod +x get_helm.sh && \
    ./get_helm.sh && rm -f get_helm.sh

# Install kubectl.
RUN if [ $(uname -m) = x86_64 ]; then \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"; \
    else \
    curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/arm64/kubectl"; \
    fi && \
    chmod +x kubectl && \
    mv kubectl /usr/local/bin/kubectl
