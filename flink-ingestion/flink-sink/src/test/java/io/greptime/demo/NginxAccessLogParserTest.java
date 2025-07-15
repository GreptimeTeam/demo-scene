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

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;

class NginxAccessLogParserTest {

    @Test
    void testParseLogLine() {
        NginxAccessLogParser parser = new NginxAccessLogParser();
        String logLine = "60.61.139.220 - - [24/Jun/2025:23:23:35 -0700] \"POST /logout HTTP/2.0\" 200 183 \"-\" \"Mozilla/5.0 (Windows NT 5.1; U; en; rv:1.8.1) Gecko/20061208 Firefox/2.0.0 Opera 9.50\"";
        Object[] result = parser.logLineToRow(logLine);

        assertNotNull(result);
        assertEquals(8, result.length);

        assertEquals(1750832615000L, result[0]); // access_time
        assertEquals("60.61.139.220", result[1]); // client
        assertEquals("POST", result[2]); // method
        assertEquals("/logout", result[3]); // uri
        assertEquals("HTTP/2.0", result[4]);  // protocol
        assertEquals(200, result[5]); // status
        assertEquals(183.0, result[6]); // size
        assertEquals("Mozilla/5.0 (Windows NT 5.1; U; en; rv:1.8.1) Gecko/20061208 Firefox/2.0.0 Opera 9.50", result[7]); // agent
    }
}
