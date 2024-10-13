apiVersion: 2
datasources:
  - name: greptimedb
    type: prometheus
    access: proxy
    url: ${GREPTIME_SCHEME:=http}://${GREPTIME_HOST:=greptimedb}:${GREPTIME_PORT:=4000}/v1/prometheus
    basicAuth: true
    basicAuthUser: ${GREPTIME_USERNAME}
    jsonData:
      httpHeaderName1: X-GREPTIME-DB-NAME
    secureJsonData:
      basicAuthPassword: ${GREPTIME_PASSWORD}
      httpHeaderValue1: ${GREPTIME_DB:=public}
    editable: false
