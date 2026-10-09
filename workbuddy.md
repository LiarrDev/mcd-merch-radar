# workbuddy.md

> 本文件记录「麦麦周边雷达」项目在 **WorkBuddy** 中的开发对话上下文，
> 用于核验 WorkBuddy 专项奖励（麦当劳程序员创意开发大赛 × WorkBuddy 联动活动）的参与条件。

---

## 一、项目概况

| 项 | 值 |
|---|---|
| 项目名称 | 麦麦周边雷达 · MCD Merch Radar |
| 项目地址 | https://github.com/LiarrDev/mcd-merch-radar |
| 一句话 | 找出各麦当劳门店当前在售的周边商品 —— 官方菜单里没有「周边」分类，它们藏在汉堡薯条中间 |
| 开发方式 | 在 WorkBuddy 中完成调研、方案设计、编码、真实联调与文档撰写 |
| 数据依赖 | 麦当劳中国 MCP（`https://mcp.mcd.cn`），全部为真实调用 |

---

## 二、WorkBuddy 中完成的工作

### 1. 赛前调研（决定做什么）

WorkBuddy 拉取并分析了官方活动仓库的 `README.md` 与 `activityGuidelines.md`，
并通过 GitHub API 统计了全部 46 个已报名项目的 Star 数与赛道分布，得出：

- 排名 100% 由 GitHub Star 数决定，定榜快照 2026-10-26 00:00
- 省钱点餐（~11 个）与营养配餐（~9 个）已是红海
- 外送地址、订单售后、得来速、问卷券等 MCP 能力**无人使用**
- 活动日历 / 情报聚合方向 5 个项目，Star 全部为 0–1

### 2. 方向验证（用真实 MCP 数据，不靠猜）

WorkBuddy 直接调用本机已配置的麦当劳 MCP 做了多轮实测：

- 拉取积分商城全量商品，发现存在「玩具」「鞋袜」类目
- 试出限定周边类目参数 `catRuleIds=2>8`，得到罗技键鼠套装、Nike Book 2 联名款等
- 发现 `mall-product-detail` 对过期商品返回 `610403 商品已下架`，可作为有效性二次校验
- 跨上海、北京、广州三城拉取完整菜单，确认**门店间周边确有差异**
- 验证开心乐园餐玩具轮次**三城完全一致**，据此判断「玩具」线做不出差异，将主线改为「在售周边」

### 3. 编码实现

在 WorkBuddy 中编写了完整项目代码（Python，零第三方依赖）：

- `merch_radar/client.py` — MCP Streamable HTTP 客户端
- `merch_radar/extract.py` — 周边识别规则
- `merch_radar/scan.py` — 跨店扫描与聚合、积分周边时间校正
- `merch_radar/render.py` — Markdown 渲染
- `merch_radar/cli.py` — 命令行入口

### 4. 真实联调

在 WorkBuddy 中执行扫描脚本，使用真实 MCP Token 跑通三城九店，
产出真实报告并固化为 `docs/sample-report.md`。运行结果：

- 扫描 3 座城市 / 9 家门店，全部成功
- 发现 7 款在售周边，其中 4 款为门店差异款
- 积分商城 3 件限定周边全部识别为已过期（接口 `status` 仍标记上架）

### 5. 文档撰写

`README.md`、`MCP_INTEGRATION.md`、`skills/mcd-merch-radar/SKILL.md` 均在
WorkBuddy 中基于真实运行数据撰写，报告中的表格为实际输出，非模拟数据。

---

## 三、真实使用麦当劳 MCP 的证据

| Tool | 是否调用 | 用途 |
|---|:--:|---|
| `now-time-info` | ✅ | 取服务器时间，校正兑换窗口 |
| `query-nearby-stores` | ✅ | 按城市取门店列表 |
| `query-meals` | ✅ | 门店在售菜单（核心数据源） |
| `query-meal-detail` | ✅ | 验证周边无选配轮次 |
| `mall-points-products` | ✅ | 积分限定周边（`catRuleIds=2>8`） |
| `mall-product-detail` | ✅ | 过期商品二次校验 |

全部为真实调用，`docs/sample-report.md` 中的表格即真实返回数据的整理结果。

---

## 四、合规说明

- 配置文件 `mcp-config.example.json` 只含环境变量占位符 `${MCD_MCP_TOKEN}`，**不含真实凭证**
- 真实 Token 仅存放于本机 `~/.workbuddy/mcp.json`，并通过环境变量注入，未进入任何仓库文件
- 项目全程只读，不调用下单、兑换、领券等写操作
- `CONTEST_DECLARATION.md` 为官方原文，未做任何修改
