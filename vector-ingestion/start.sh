[ ! -f start.env ] || export $(grep -v '^#' start.env | xargs)

GT_SCHEMA=${GT_SCHEMA-:https}

if [ -z "$GT_SCHEMA" ]; then
  echo "GT_SCHEMA is not set"
  exit 1
fi

if [ -z "$GT_HOST" ]; then
  echo "GT_HOST is not set"
  exit 1
fi

if [ -z "$GT_DB_NAME" ]; then
  echo "GT_DB_NAME is not set"
  exit 1
fi

function create_pipeline {
## if GT_USERNAME and GT_PASSWORD are not set, then disable basic auth

if [ -z "$GT_USERNAME" ] || [ -z "$GT_PASSWORD" ];
then
  echo "GT_USERNAME or GT_PASSWORD is not set, disabling basic auth"
  curl -X "POST" "$GT_SCHEMA://$GT_HOST:$GT_HTTP_PORT/v1/events/pipelines/apache_common_pipeline?db=$GT_DB_NAME" \
    -F "file=@pipeline.yaml"
else
  echo "GT_USERNAME and GT_PASSWORD are set, enabling basic"
  curl -X "POST" "$GT_SCHEMA://$GT_HOST:$GT_HTTP_PORT/v1/events/pipelines/apache_common_pipeline?db=$GT_DB_NAME" \
     -u "$GT_USERNAME:$GT_PASSWORD" \
     -F "file=@pipeline.yaml"
fi 
}

function run_demo {

## if GT_GRPC_TLS is true set example.toml to use tls
if [ "$GT_GRPC_TLS" = "true" ];
then
  echo "GT_GRPC_TLS is true, setting example.toml grpc to use tls"
  sed -i 's/#tls = {}/tls = {}/g' example.toml
else
  echo "GT_GRPC_TLS is not set or false, setting example.toml grpc to not use tls"
  sed -i 's/tls = {}/#tls = {}/g' example.toml
fi

podman run \
  --env-file start.env \
  --rm \
  -v $PWD/example.toml:/etc/vector/vector.toml:ro \
  --name vector \
  --network host \
  timberio/vector:0.42.0-debian  --config-toml /etc/vector/vector.toml

}

## two subcommands are supported, create_pipeline and run_demo
case "$1" in
  create_pipeline)
    create_pipeline
    ;;
  run_demo)
    run_demo
    ;;
  *)
    echo "Usage: $0 {create_pipeline|run_demo}"
    exit 1
    ;;
esac