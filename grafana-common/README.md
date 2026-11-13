# Dashboard languages

The Grafana root URL redirects to an English or Chinese dashboard using the browser's preferred `Accept-Language`. A first language starting with `zh` selects Chinese; other languages select English. Explicit dashboard URLs keep their selected language. Grafana's own UI uses `GF_USERS_DEFAULT_LANGUAGE=detect`.

Dashboard links switch languages and preserve the time range and template variables. SQL, PromQL, datasource UIDs, and variable values are identical in both versions.

After changing an English dashboard or a translation in `zh-CN.json`:

```sh
python3 grafana-common/localize.py
python3 grafana-common/localize.py --check
```

The check runs in CI. OTel playground maintains its own paired dashboards; its `verify.py` checks query parity and live query results.
