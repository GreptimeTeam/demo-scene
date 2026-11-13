FROM maven:3.9-eclipse-temurin-11 AS builder
WORKDIR /build
COPY flink-sink/pom.xml ./
COPY flink-sink/src ./src
RUN mvn -B package

FROM flink:1.20.1-java11
COPY --from=builder /build/target/flink-demo-0.1.0.jar flink-demo.jar
COPY flink-demo/run.sh .
CMD ["sh", "./run.sh"]
