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

import io.greptime.BulkStreamWriter;
import io.greptime.models.Table;
import org.apache.flink.api.connector.sink2.SinkWriter;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.concurrent.CompletableFuture;

class GreptimeSinkWriter implements SinkWriter<String> {

    private static final Logger LOGGER = LoggerFactory.getLogger(GreptimeSinkWriter.class);

    private static final int MAX_ACCUMULATED_ROWS = 1_000;

    private final BulkStreamWriter writer;
    private final NginxAccessLogParser parser = new NginxAccessLogParser();
    private Table.TableBufferRoot buffer;
    private int accumulated_rows = 0;

    GreptimeSinkWriter(BulkStreamWriter writer) {
        this.writer = writer;
        this.buffer = createRowBuffer();
    }

    Table.TableBufferRoot createRowBuffer() {
        return writer.tableBufferRoot(MAX_ACCUMULATED_ROWS);
    }

    @Override
    public void write(String logLine, Context context) {
        Object[] row = parser.logLineToRow(logLine);
        buffer.addRow(row);

        if (++accumulated_rows >= MAX_ACCUMULATED_ROWS) {
            insert();
        }
    }

    @Override
    public void flush(boolean endOfInput) {
        if (accumulated_rows == 0) {
            return;
        }
        insert();
    }

    void insert() {
        buffer.complete();

        long start = System.currentTimeMillis();
        try {
            CompletableFuture<Integer> future = writer.writeNext();
            Integer rows = future.get();
            LOGGER.info("Insert {} rows, time cost: {} millis", rows, System.currentTimeMillis() - start);
        } catch (Exception e) {
            throw new RuntimeException(e);
        }

        buffer = createRowBuffer();
        accumulated_rows = 0;
    }

    @Override
    public void close() throws Exception {
        writer.close();
    }
}