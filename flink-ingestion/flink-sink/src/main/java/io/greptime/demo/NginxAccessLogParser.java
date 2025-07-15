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

import java.time.OffsetDateTime;
import java.time.format.DateTimeFormatter;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

class NginxAccessLogParser {

    // Example log line:
    // 60.61.139.220 - - [24/Jun/2025:23:23:35 -0700] "POST /logout HTTP/2.0" 200 183 "-" "Mozilla/5.0 (Windows NT 5.1; U; en; rv:1.8.1) Gecko/20061208 Firefox/2.0.0 Opera 9.50"
    private static final Pattern NGINX_LOG_PATTERN = Pattern.compile(
            "^(?<client>\\S+) \\S+ \\S+ \\[(?<timestamp>[\\w:/]+\\s[+\\-]\\d{4})] " +
                    "\"(?<method>\\S+)\\s+(?<uri>\\S+)\\s+(?<protocol>\\S+)\" " +
                    "(?<status>\\d{3}) (?<size>\\d+) \"(?<referer>[^\"]*)\" \"(?<agent>[^\"]*)\".*$"
    );

    // Nginx timestamp format: dd/MMM/yyyy:HH:mm:ss Z
    private static final DateTimeFormatter NGINX_TIMESTAMP_FORMATTER =
            DateTimeFormatter.ofPattern("dd/MMM/yyyy:HH:mm:ss Z", Locale.ENGLISH);

    Object[] logLineToRow(String line) {
        Matcher matcher = NGINX_LOG_PATTERN.matcher(line);
        if (!matcher.matches()) {
            throw new IllegalArgumentException("Failed to parse log line: \"" + line + "\", pattern not matched");
        }

        String timestampStr = matcher.group("timestamp");
        String client = matcher.group("client");
        String method = matcher.group("method");
        String uri = matcher.group("uri");
        String protocol = matcher.group("protocol");
        int status = Integer.parseInt(matcher.group("status"));
        double size = Double.parseDouble(matcher.group("size"));
        String agent = matcher.group("agent");

        // Timestamp: Nginx logs are typically local time with an offset.
        // GreptimeDB expects TimestampMillisecond (UTC milliseconds usually)
        OffsetDateTime odt = OffsetDateTime.parse(timestampStr, NGINX_TIMESTAMP_FORMATTER);
        long accessTimeMillis = odt.toInstant().toEpochMilli();

        // Ensure the order matches your GreptimeDB tableSchema
        return new Object[]{
                accessTimeMillis, // access_time (TimestampMillisecond)
                client,           // client (String)
                method,           // method (String)
                uri,              // uri (String)
                protocol,         // protocol (String)
                status,           // status (UInt8)
                size,             // size (Float64)
                agent             // agent (String)
        };
    }
}
