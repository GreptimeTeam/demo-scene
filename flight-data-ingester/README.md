# GreptimeDB Flight

This project demonstrates GreptimeDB's ingesting geo-spatial data using the the `greptimedb-ingester-go` client. It selects the last 10 flights that departed in the last 30 minutes from the configured icao airport code. The ingester script utilizes the [OpenSky Network API](https://opensky-network.org/apidoc/) to fetch flight state data and inserts the flight metrics into GreptimeDB

## How to run this demo

Ensure you have `git`, `docker`, `docker-compose`
installed. To run this demo:

```shell
git clone https://github.com/GreptimeTeam/demo-scene.git
cd demo-scene/flight-data-ingester
docker compose up
```

It can take a while for the first run to pull down images and also build necessary components.

## How it works

The topology is illustrated in this diagram.

```mermaid
flowchart LR
  greptimedb[(GreptimeDB)]

  api{Open Sky Data} --> go-ingester
  go-ingester --> greptimedb
```

after GreptimeDB starts, we use the `ingester` script which uses the go client's [high level api](https://docs.greptime.com/user-guide/ingest-data/for-iot/grpc-sdks/go/#installation) to create the table and insert data. It's dead-simple to perform transformations and data munging on your struct and insert into target GreptimeDB columns by tagging your metric struct accordingly as seen in the `./ingester/dto.go` file .

## Note

please update the ICAO flight code for your local airport of the city you are
running the demo in to ensure there is data in the set. This can be done by
setting the ``ICAO_AIRPORT_CODE` environment variable when running `docker
compose up`.

If you are going to restart this demo, press `Ctrl-C` and remember to call
`docker compose down` to clean up the data before you run `docker compose up`
again.
