/*
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package io.greptime.demo;

import io.greptime.GreptimeDB;
import io.greptime.models.DataType;
import io.greptime.models.TableSchema;
import io.greptime.options.GreptimeOptions;
import org.apache.commons.lang3.StringUtils;
import org.apache.flink.api.connector.sink2.Sink;
import org.apache.flink.api.connector.sink2.SinkWriter;
import org.apache.flink.api.connector.sink2.WriterInitContext;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

class GreptimeSink implements Sink<String> {

    private static final Logger LOGGER = LoggerFactory.getLogger(GreptimeSink.class);

    @Override
    public SinkWriter<String> createWriter(@SuppressWarnings("deprecation") InitContext context) {
        throw new UnsupportedOperationException();
    }

    @Override
    public SinkWriter<String> createWriter(WriterInitContext context) {
        String endpoint = StringUtils.defaultIfEmpty(
                System.getenv("GREPTIMEDB_ENDPOINT"),
                "127.0.0.1:4001");
        LOGGER.info("Connecting to GreptimeDB at endpoint: {}", endpoint);

        GreptimeDB greptimeDb = GreptimeDB.create(GreptimeOptions.newBuilder(endpoint, "public").build());

        TableSchema tableSchema = TableSchema.newBuilder("nginx_access_log")
                .addTimestamp("access_time", DataType.TimestampMillisecond)
                .addField("client", DataType.String)
                .addField("method", DataType.String)
                .addField("uri", DataType.String)
                .addField("protocol", DataType.String)
                .addField("status", DataType.UInt16)
                .addField("size", DataType.Float64)
                .addField("agent", DataType.String)
                .build();

        return new GreptimeSinkWriter(greptimeDb.bulkStreamWriter(tableSchema));
    }
}
