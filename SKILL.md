---
slug: risk-radar
displayName: 企业风险雷达
summary: >
  Enterprise risk assessment and sentiment monitoring tool using akshare
  for real Chinese stock/company data. Computes 6-dimension risk scores
  (debt ratio, cash flow, pledge, goodwill, litigation, profitability),
  monitors news sentiment, and generates interactive HTML dashboards.
tags:
  - risk
  - enterprise
  - sentiment
  - monitor
  - akshare
  - stock
  - finance
license: MIT
---

# 企业风险雷达 (Risk Radar)

## Description

An enterprise risk assessment and sentiment monitoring tool for Chinese A-share
stocks. It pulls **real data** via [akshare](https://github.com/akfamily/akshare)
from East Money and THS, computes six risk dimensions, scores them on a 0-100
scale (lower = riskier), generates traffic-light indicators, and produces a
self-contained interactive HTML dashboard with a radar chart.

## Use Cases

1. **Quick risk scan** for a single stock before making investment decisions.
2. **Batch screening** of a watchlist to rank companies by risk score.
3. **Sentiment monitoring** to gauge market perception of a specific company.
4. **Due diligence** on potential suppliers, partners, or investment targets.
5. **Periodic monitoring** via cron/CI to alert on risk changes.

## How to Use

### Installation

```bash
pip install -r requirements.txt
```

### Quick start

```bash
# Scan a single stock (risk + sentiment + HTML report)
python radar.py scan --ticker 600519

# Scan without sentiment analysis
python radar.py scan --ticker 000858 --no-sentiment

# Generate report to specific path
python radar.py scan --ticker 601318 --output report.html

# Sentiment-only monitoring
python radar.py monitor --ticker 600519

# Batch scan multiple stocks
python radar.py batch --tickers 600519,000858,601318
```

### CLI Commands

| Command | Description |
|---------|-------------|
| `scan --ticker CODE` | Full risk scan + sentiment + HTML report |
| `scan --ticker CODE --no-sentiment` | Risk scan only, skip sentiment |
| `monitor --ticker CODE` | Sentiment/opinion monitoring only |
| `batch --tickers A,B,C` | Batch scan multiple tickers, sort by risk |

### Risk Dimensions

| Dimension | Key | Scoring Logic |
|-----------|-----|---------------|
| 资产负债率 (Debt Ratio) | `debt_ratio` | <40% = 95pts; 40-55% = 80pts; 55-70% = 60pts; 70-85% = 30pts; >85% = 10pts |
| 现金流覆盖 (Cash Flow) | `cash_flow` | Operating cash flow / current liabilities ratio |
| 股权质押 (Pledge) | `pledge` | <10% = 95pts; 10-20% = 80pts; 20-40% = 60pts; 40-60% = 30pts; >60% = 10pts |
| 商誉占比 (Goodwill) | `goodwill` | Goodwill / net equity ratio |
| 诉讼风险 (Litigation) | `litigation` | Keyword detection from news: 90pts or 20pts |
| 盈利能力 (Profitability) | `profitability` | Net margin percentage |

### Traffic Light Levels

| Score Range | Level | Meaning |
|-------------|-------|---------|
| 70-100 | Green | Low risk, fundamentals solid |
| 40-69 | Yellow | Moderate risk, attention needed |
| 0-39 | Red | High risk, significant concerns |

## Data Sources

All data is fetched via akshare from publicly available Chinese financial data platforms:

- **Financial data**: East Money (东方财富) and THS (同花顺) via `stock_financial_abstract_ths()`, `stock_financial_analysis_indicator()`
- **Pledge data**: East Money via `stock_em_gpzy_pledge_ratio_detail()`
- **News/sentiment**: East Money via `stock_news_em()`
- **Company info**: East Money via `stock_individual_info_em()`

## Output

The `scan` command generates a self-contained HTML file with:

- Radar chart showing all 6 risk dimensions
- Traffic light overall score indicator
- Per-dimension detail cards
- Risk warnings section
- Sentiment timeline with news headlines
- Summary statistics (positive/negative/neutral counts)

## Architecture

```
risk-radar/
├── radar.py              # Click-based CLI entry point
├── risk_radar/
│   ├── __init__.py       # Package init
│   ├── scanner.py         # Risk data fetching + scoring engine
│   ├── sentiment.py       # News sentiment analysis
│   └── report.py          # HTML dashboard generator
├── SKILL.md              # This skill definition
├── README.md             # Project README
└── requirements.txt      # Python dependencies
```

## Configuration

No API keys required. All data is sourced from free public APIs via akshare.

## Notes

- Data is for reference only and does not constitute investment advice.
- Financial data APIs are subject to rate limiting from upstream providers.
- The first run may be slow as akshare caches some configuration.
