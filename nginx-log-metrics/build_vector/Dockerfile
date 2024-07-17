# Use Rust as the base image
FROM rust:1.79 as builder

# Install system dependencies
RUN apt-get update && apt-get install -y cmake pkg-config libssl-dev protobuf-compiler libsasl2-dev

# Clone the Vector source code
RUN git clone --depth 1 https://github.com/shuiyisong/vector.git /vector
WORKDIR /vector

# Switch to your custom branch
RUN git checkout chore/greptime_log_ingester

# Build Vector
RUN cargo build --release --no-default-features --features=default-greptimedb-custom,sinks-console,sources-prometheus-scrape,sources-prometheus-scrape

# Use a minimal base image for the final image
FROM debian:bookworm-slim

# Copy the Vector binary from the builder stage
COPY --from=builder /vector/target/release/vector /usr/local/bin/vector

# Set up the config directory
ENV VECTOR_CONFIG_LOCATION "/etc/vector/vector.toml"

# Define the entry point
CMD vector -c $VECTOR_CONFIG_LOCATION
