# Risk Radar - 企业风险雷达

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

基于 [akshare](https://github.com/akfamily/akshare) 真实财报数据的企业风险评估与舆情监控工具。

## 功能特性

- **六维风险扫描**：资产负债率、现金流覆盖、股权质押、商誉占比、诉讼风险、盈利能力
- **智能评分**：0-100 分制，红黄绿三色交通灯告警
- **舆情监控**：基于新闻标题关键词的情感分析（正面/负面/中性）
- **HTML 看板**：交互式雷达图 + 维度详情 + 舆情时间线，一个 HTML 文件即可分享
- **批量扫描**：支持一键扫描多只股票，按风险评分排序
- **零配置**：无需 API Key，数据完全来自公开接口

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 基本用法

```bash
# 扫描单只股票（风险+舆情+HTML报告）
python radar.py scan --ticker 600519

# 跳过舆情分析
python radar.py scan --ticker 000858 --no-sentiment

# 输出到指定路径
python radar.py scan --ticker 601318 --output 我的报告.html

# 仅舆情监控
python radar.py monitor --ticker 600519

# 批量扫描
python radar.py batch --tickers 600519,000858,601318
```

### 输出示例

```
Risk Radar - 扫描 600519

贵州茅台 (600519)
综合评分: 88/100 - 低风险

维度            原始值    评分  等级
──────────────────────────────────
资产负债率       19.5%     95  ✅ 低负债
现金流覆盖        0.85     95  ✅ 现金流充裕
股权质押          0.0%     95  ✅ 无质押
商誉占比          0.0%     95  ✅ 商誉极低
诉讼风险            否     90  ✅ 无诉讼
盈利能力         52.1%     90  ✅ 高利润率

HTML 报告已保存至: risk_radar_600519_20260706_210000.html
```

## 六维风险评分逻辑

| 维度 | 评分区间 | 说明 |
|------|---------|------|
| 资产负债率 | <40%=95分, 40-55%=80分, 55-70%=60分, 70-85%=30分, >85%=10分 | 负债越低越安全 |
| 现金流覆盖 | >1.0=95分, 0.5-1.0=75分, 0.2-0.5=55分, <0.2=25分, 负=10分 | 经营现金流/流动负债 |
| 股权质押 | <10%=95分, 10-20%=80分, 20-40%=60分, 40-60%=30分, >60%=10分 | 质押越低越安全 |
| 商誉占比 | <5%=95分, 5-15%=80分, 15-30%=60分, 30-50%=30分, >50%=10分 | 商誉/净资产 |
| 诉讼风险 | 无=90分, 有=20分 | 基于新闻关键词检测 |
| 盈利能力 | >15%=90分, 5-15%=70分, 0-5%=40分, <0=10分 | 净利率 |

> 综合评分 = 各维度加权平均（负债20% + 现金流20% + 质押15% + 商誉15% + 诉讼15% + 盈利15%）

## 交通灯系统

| 评分 | 等级 | 含义 |
|------|------|------|
| 70-100 | 🟢 绿色 | 低风险，基本面稳健 |
| 40-69 | 🟡 黄色 | 中等风险，需要关注 |
| 0-39 | 🔴 红色 | 高风险，存在重大问题 |

## 数据来源

全部数据通过 akshare 从以下平台获取：

- **财务数据**：东方财富、同花顺
  - `stock_financial_abstract_ths()` — 财务摘要（含资产负债率、商誉、净资产）
  - `stock_financial_analysis_indicator()` — 财务分析指标（含现金流量比率、净利率）
- **质押数据**：`stock_em_gpzy_pledge_ratio_detail()` — 东方财富股权质押
- **新闻舆情**：`stock_news_em()` — 东方财富个股新闻
- **基本信息**：`stock_individual_info_em()` — 公司名称等

## 项目结构

```
risk-radar/
├── radar.py                 # CLI 入口 (Click)
├── risk_radar/
│   ├── __init__.py          # 包初始化
│   ├── scanner.py           # 风险扫描引擎（数据获取+评分）
│   ├── sentiment.py         # 舆情分析（关键词情感匹配）
│   └── report.py            # HTML 交互式看板生成器
├── SKILL.md                 # Skill 定义文件
├── README.md                # 本文件
└── requirements.txt         # Python 依赖
```

## 依赖

- `akshare>=1.14.0` — 金融数据接口
- `pandas>=2.0.0` — 数据处理
- `numpy>=1.24.0` — 数值计算
- `click>=8.0.0` — CLI 框架
- `rich>=13.0.0` — 终端美化输出（可选）

## 免责声明

本工具所有数据和评分仅供学习研究参考，不构成任何投资建议。投资有风险，入市需谨慎。

## License

MIT License
