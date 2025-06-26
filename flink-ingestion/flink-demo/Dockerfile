FROM adoptopenjdk/openjdk11:jdk-11.0.9.1_1 AS builder

RUN apt-get update && \
    apt-get install -y git maven

WORKDIR /build

RUN git clone https://github.com/GreptimeTeam/flink-demo.git . && \
    mvn package


FROM flink:1.20.1-java11

COPY --from=builder /build/target/flink-demo-0.1.0.jar flink-demo.jar
COPY run.sh .

CMD ["sh", "./run.sh"]
