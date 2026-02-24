---
name: market-state
description: 用 AKShare 生成“市场行情整理”（A股全市场广度、涨跌幅分布、成交额Top等），输出严格 JSON。
---

# Market State（市场行情整理）

## 目的
给出“今天市场行情整理”的结构化结果（用于复盘/日报/叙事市场Agent底座）。

## 运行要求
- 需要本机能运行 python 且已安装 akshare
- 只能做数据拉取与摘要，不执行下单/交易、不修改任何账户

## 输入参数（由用户自然语言决定）
- scope：默认 hs_a
- params：可选 JSON
  - top_n: 默认 20
  - raw: 默认 false
  - raw_rows: 默认 2（当 raw=true 时）

## 执行步骤（必须使用 exec 工具）
1) 在当前 skill 目录下运行脚本，始终以 JSON 输出：
   - 无参数：`python market_state.py`
   - 带参数：`python market_state.py hs_a '{"top_n": 20, "raw": false}'`

2) 如果返回包含 `error`：
   - 先把 `error` 原样返回
   - 再给出 1-2 条最可能原因（网络/数据源风控/代理）
   - 不要猜测具体行情结论

3) 如果成功：
   - 直接返回脚本输出 JSON（原样），不要改字段名
   - 在 JSON 之后补一段 5-8 行的“人类可读摘要”，只引用 JSON 里的数值

## 输出格式
- 第一段：严格 JSON（脚本原样输出）
- 第二段：可读摘要（不超过 8 行）
