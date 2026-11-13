# GreptimeDB Observability Playground

[English](README.md) | 简体中文

使用 OpenTelemetry Astronomy Shop 产生流量，将 metrics、logs 和 traces 存入 GreptimeDB。Grafana 大盘覆盖服务、日志、调用链和主机指标，提供中英文版本。

概览大盘包含一条 SQL，按分钟关联请求量、应用日志和主机内存。Flow 每 30 秒计算各服务的请求数和错误数。

## 运行

需要 Docker（含 Compose）、Git 和 Python 3.11+。启动 Docker 后执行：

```bash
git clone https://github.com/GreptimeTeam/demo-scene.git
cd demo-scene/opentelemetry-playground
python3 demo.py up
```

首次运行会下载固定版本的镜像。负载生成器自动产生购物流量，遥测数据需要一段时间写入。

- [商店](http://localhost:18080)
- [Grafana](http://localhost:13000) · [中文大盘](http://localhost:13000/d/astronomy-shop-greptimedb-zh)
- [GreptimeDB](http://localhost:24000/dashboard)

Grafana 根路径按浏览器首选语言选择大盘。大盘顶部的 **English / 简体中文** 链接切换语言，保留时间范围和筛选条件。

## 演示支付故障

1. 在[故障开关](http://localhost:18080/feature)中将 `paymentFailure` 设为 `100%`。该开关影响 demo 的所有支付请求。
2. 在商店结账，或等待自动流量。结账接口返回 HTTP 422 和 `PAYMENT_FAILED`。
3. 在 Grafana 的服务大盘选择 `payment`，从「最近请求 · 错误优先」表中打开一条调用链。
4. 查看 `checkout` → `payment` 的 spans，按 `WARN` 和 `Invalid token` 筛选支付错误日志。
5. 将 `paymentFailure` 恢复为 `off`，确认结账成功。中途停止演示时也需关闭该开关。

## 验证与停止

关闭支付故障开关后执行：

```bash
python3 verify.py
python3 demo.py logs otel-collector init-flows
python3 demo.py down
```

验证脚本检查下单、遥测入库和中英文共 80 个数据面板，失败时返回非零退出码，不验证浏览器交互。`down` 移除本项目容器，保留 GreptimeDB 数据卷。

## 运行说明

- Grafana 允许匿名 Admin 访问。发布端口绑定 `127.0.0.1`；node_exporter 使用 host 网络，在 9100 端口监听。
- macOS 上的主机指标来自 Docker / OrbStack Linux VM。容器内存包含同一 Docker host 上的所有项目。
- 请求量只统计 server spans。延迟分位数为近似值，Flow 当前分钟的计数尚未完整。SQL 按时间关联数据，不表示因果关系。
- 调用链详情加载指定 Trace ID 的全部已存储 spans；日志仍受大盘时间范围和筛选条件限制。
- 启动脚本使用 `demo-scene-otel-playground` Compose 项目，生成文件保存在 `.runtime/`。Collector 配置见 [otelcol-config-greptime.yml](otelcol-config-greptime.yml)，采集目标见 [prometheus.yml](prometheus.yml)。
