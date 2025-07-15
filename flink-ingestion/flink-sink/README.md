# GreptimeDB Apache Flink Sink Example

This is an example of writing an Apache Flink sink for GreptimeDB. To make the example meaningful, it can be ran as a demo of ingesting Nginx access logs into GreptimeDB.

## How to Run

We provide a simple way to see this demo running directly: you can check out the docker compose file in the parent directory.

If you prefer to run the demo manually, you can follow the steps below.

0. **Prerequisites**

* **Java Development Kit (JDK) 11 or later**.
* **Apache Maven**: Used for building the project.

1. **Clone the repository**:

   ```bash
   git clone https://github.com/GreptimeTeam/demo-scene.git
   cd demo-scene/flink-ingestion/flink-sink
   ```

2. **Build the project**:
   This will create a fat JAR containing all necessary dependencies.

   ```bash
   mvn package
   ```

3. **Start the required services**

    * **GreptimeDB**: You can find installation
      instructions [here](https://docs.greptime.com/getting-started/installation/overview). Make sure to create the
      `nginx_access_log` table:
      ```sql
      CREATE TABLE IF NOT EXISTS nginx_access_log (
        access_time TIMESTAMP TIME INDEX,
        client STRING,
        "method" STRING,
        uri STRING,
        protocol STRING,
        "status" UINT16,
        size DOUBLE,
        agent STRING,
      )
      WITH (
        append_mode = 'true'
      );
      ```
    * **Apache Kafka**: A running Kafka instance with a topic named `nginx_access_log`. This demo uses Kafka to consume
      Nginx access logs.
    * **Apache Flink**: A running Apache Flink cluster or a local Apache Flink setup. This demo is built with Apache
      Flink version 1.20.1.
    * **Nginx access logs generator**: You can actually run a Nginx server to generate the access logs. Or you can check
      out our simple python script [here](https://github.com/GreptimeTeam/demo-scene/flink-ingestion/producer/app.py) to
      generate some fake ones.

4. **Configure Environment Variables (Optional)**:
   You can set the following environment variables to override default connection settings:

    * `KAFKA_BOOTSTRAP_SERVERS`: Kafka bootstrap servers (default: `127.0.0.1:9092`)
    * `GREPTIMEDB_ENDPOINT`: GreptimeDB endpoint for GRPC interface (default: `127.0.0.1:4001`)

   Example:
   ```bash
   export KAFKA_BOOTSTRAP_SERVERS=your_kafka_host:9092
   export GREPTIMEDB_ENDPOINT=your_greptimedb_host:4001
   ```

5. **Run the Flink application**:
   Submit the fat JAR in step 2 to your Apache Flink cluster. Replace `target/flink-demo-0.1.0.jar` with the actual path
   to your built JAR file.

   ```bash
   flink run target/flink-demo-0.1.0.jar
   ```

   This command will start the Apache Flink job, which will consume messages from the `nginx_access_log` Kafka topic,
   parse them, and ingest them into GreptimeDB.

## Code Explanation

The project consists of the following main components:

* `NginxAccessLogIngester.java`: This is the main entry point of the Apache Flink application. It sets up the Apache
  Flink execution environment, configures the Kafka source to read Nginx access logs, and pipes the data to the
  `GreptimeSink`.
* `GreptimeSink.java`: This class implements the Apache Flink `Sink` interface. It initializes the GreptimeDB client and
  defines the schema for the `nginx_access_log` table in GreptimeDB.
* `GreptimeSinkWriter.java`: This class implements the Apache Flink `SinkWriter` interface. By utilizing the new "bulk
  insert" feature introduced in GreptimeDB since version 0.15, it can efficiently ingest large volume of data into
  GreptimeDB.
