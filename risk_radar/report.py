"""HTML 风险看板 —— 生成交互式雷达图 + 交通灯 + 情绪时间线"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Optional

from .scanner import RiskReport
from .sentiment import SentimentReport

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dimension order & labels
# ---------------------------------------------------------------------------

DIM_ORDER = ["debt_ratio", "cash_flow", "pledge", "goodwill", "litigation", "profitability"]
DIM_LABELS_CN = {
    "debt_ratio": "资产负债率",
    "cash_flow": "现金流覆盖",
    "pledge": "股权质押",
    "goodwill": "商誉占比",
    "litigation": "诉讼风险",
    "profitability": "盈利能力",
}


class ReportGenerator:
    """HTML 风险看板生成器"""

    @staticmethod
    def generate(
        risk: RiskReport,
        sentiment: Optional[SentimentReport] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """生成完整 HTML 看板并保存到文件"""
        html = ReportGenerator._build_html(risk, sentiment)

        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)
            logger.info("Report saved to %s", output_path)

        return html

    # ------------------------------------------------------------------
    # HTML assembly
    # ------------------------------------------------------------------

    @staticmethod
    def _build_html(risk: RiskReport, sentiment: Optional[SentimentReport]) -> str:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        dims_data = []
        for key in DIM_ORDER:
            for d in risk.dimensions:
                if d.key == key:
                    dims_data.append(d)
                    break

        radar_labels = [DIM_LABELS_CN.get(d.key, d.name) for d in dims_data]
        radar_scores = [d.score for d in dims_data]

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>风险雷达 - {risk.company_name} ({risk.ticker})</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC",
                 "Microsoft YaHei", sans-serif;
    background: #0f172a; color: #e2e8f0; line-height: 1.6;
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
.header {{
    text-align: center; padding: 32px 0 20px;
    border-bottom: 2px solid #1e293b; margin-bottom: 28px;
}}
.header h1 {{ font-size: 28px; color: #f8fafc; }}
.header .subtitle {{ color: #94a3b8; font-size: 14px; margin-top: 6px; }}
.company-info {{
    display: flex; align-items: center; justify-content: center;
    gap: 16px; margin-top: 10px;
}}
.company-name {{ font-size: 20px; font-weight: 600; color: #38bdf8; }}
.company-ticker {{ color: #64748b; font-size: 14px; }}

/* Traffic light */
.overall-score {{
    display: flex; align-items: center; justify-content: center;
    gap: 20px; margin: 20px 0; flex-wrap: wrap;
}}
.score-circle {{
    width: 100px; height: 100px; border-radius: 50%;
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; font-weight: 700; border: 4px solid;
}}
.score-circle .number {{ font-size: 32px; line-height: 1; }}
.score-circle .label {{ font-size: 12px; opacity: 0.8; }}
.badge {{
    display: inline-block; padding: 6px 16px; border-radius: 9999px;
    font-weight: 600; font-size: 14px;
}}
.bg-green {{ background: #166534; color: #4ade80; }}
.bg-yellow {{ background: #713f12; color: #facc15; }}
.bg-red {{ background: #7f1d1d; color: #f87171; }}
.border-green {{ border-color: #4ade80; background: #14532d; color: #4ade80; }}
.border-yellow {{ border-color: #facc15; background: #422006; color: #facc15; }}
.border-red {{ border-color: #f87171; background: #450a0a; color: #f87171; }}

/* Grid layout */
.grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }}
@media (max-width: 768px) {{ .grid-2 {{ grid-template-columns: 1fr; }} }}
.card {{
    background: #1e293b; border: 1px solid #334155;
    border-radius: 12px; padding: 20px;
}}
.card h3 {{ font-size: 16px; color: #cbd5e1; margin-bottom: 16px;
             border-bottom: 1px solid #334155; padding-bottom: 10px; }}

/* Radar chart container */
.radar-container {{
    display: flex; justify-content: center; align-items: center;
    min-height: 380px;
}}
.radar-container canvas {{ max-width: 100%; max-height: 400px; }}

/* Dimension list */
.dim-list {{ display: flex; flex-direction: column; gap: 10px; }}
.dim-item {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 10px 14px; background: #0f172a; border-radius: 8px;
    border-left: 4px solid #475569;
}}
.dim-item .dim-name {{ font-size: 14px; font-weight: 500; }}
.dim-item .dim-score {{ font-size: 18px; font-weight: 700; }}
.dim-item .dim-detail {{ font-size: 12px; color: #94a3b8; }}
.dim-item.border-l-green {{ border-left-color: #4ade80; }}
.dim-item.border-l-yellow {{ border-left-color: #facc15; }}
.dim-item.border-l-red {{ border-left-color: #f87171; }}

/* Warnings */
.warnings {{ margin-top: 16px; }}
.warning-item {{
    display: flex; align-items: flex-start; gap: 8px;
    padding: 10px 14px; background: #450a0a; border: 1px solid #7f1d1d;
    border-radius: 8px; margin-bottom: 8px; font-size: 13px;
    color: #fca5a5;
}}
.warning-icon {{ font-size: 16px; flex-shrink: 0; }}

/* Sentiment timeline */
.timeline {{ display: flex; flex-direction: column; gap: 8px; max-height: 400px; overflow-y: auto; }}
.timeline-item {{
    display: flex; align-items: center; gap: 12px;
    padding: 8px 12px; background: #0f172a; border-radius: 6px;
    font-size: 13px;
}}
.timeline-dot {{
    width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
}}
.dot-green {{ background: #4ade80; }}
.dot-yellow {{ background: #facc15; }}
.dot-red {{ background: #f87171; }}
.dot-gray {{ background: #64748b; }}
.timeline-date {{ color: #64748b; font-size: 12px; min-width: 80px; }}
.timeline-title {{ flex: 1; color: #cbd5e1; }}

/* Summary bar */
.summary-bar {{
    display: flex; gap: 16px; justify-content: center; flex-wrap: wrap;
    margin: 16px 0;
}}
.summary-stat {{
    text-align: center; padding: 10px 20px; background: #0f172a;
    border-radius: 8px;
}}
.summary-stat .stat-value {{ font-size: 22px; font-weight: 700; }}
.summary-stat .stat-label {{ font-size: 12px; color: #64748b; }}

/* Footer */
.footer {{
    text-align: center; padding: 20px; color: #475569;
    font-size: 12px; border-top: 1px solid #1e293b; margin-top: 24px;
}}
</style>
</head>
<body>
<div class="container">

<!-- Header -->
<div class="header">
    <h1>风险雷达 Risk Radar</h1>
    <div class="company-info">
        <span class="company-name">{risk.company_name}</span>
        <span class="company-ticker">{risk.ticker}</span>
    </div>
    <div class="subtitle">报告生成时间: {now} | 数据来源: 东方财富 / 同花顺</div>
</div>

<!-- Overall Score -->
<div class="overall-score">
    <div class="score-circle border-{risk.overall_level}">
        <span class="number">{risk.overall_score}</span>
        <span class="label">综合评分</span>
    </div>
    <span class="badge bg-{risk.overall_level}">{ReportGenerator._level_cn(risk.overall_level)}</span>
</div>

<!-- Warnings (if any) -->
{ReportGenerator._warnings_html(risk)}

<!-- Grid: Radar + Dimensions -->
<div class="grid-2">
    <div class="card">
        <h3>六维风险雷达图</h3>
        <div class="radar-container">
            <canvas id="radarChart"></canvas>
        </div>
    </div>
    <div class="card">
        <h3>风险维度详情</h3>
        <div class="dim-list">
            {ReportGenerator._dimensions_html(dims_data)}
        </div>
    </div>
</div>

<!-- Sentiment (if available) -->
{ReportGenerator._sentiment_html(sentiment)}

<!-- Footer -->
<div class="footer">
    Risk Radar - 企业风险雷达 | 数据仅供参考, 不构成投资建议
</div>
</div>

<script>
// Radar chart
const ctx = document.getElementById('radarChart').getContext('2d');
new Chart(ctx, {{
    type: 'radar',
    data: {{
        labels: {json.dumps(radar_labels, ensure_ascii=False)},
        datasets: [{{
            label: '风险评分 (0-100)',
            data: {json.dumps(radar_scores)},
            backgroundColor: 'rgba(56, 189, 248, 0.15)',
            borderColor: 'rgba(56, 189, 248, 0.8)',
            borderWidth: 2,
            pointBackgroundColor: {json.dumps([
                "#4ade80" if s >= 70 else "#facc15" if s >= 40 else "#f87171"
                for s in radar_scores
            ])},
            pointBorderColor: '#fff',
            pointRadius: 5,
            pointHoverRadius: 7,
        }}],
    }},
    options: {{
        responsive: true,
        maintainAspectRatio: true,
        scales: {{
            r: {{
                beginAtZero: true,
                max: 100,
                min: 0,
                ticks: {{
                    stepSize: 20,
                    color: '#64748b',
                    backdropColor: 'transparent',
                    font: {{ size: 10 }},
                }},
                grid: {{ color: 'rgba(51, 65, 85, 0.5)' }},
                angleLines: {{ color: 'rgba(51, 65, 85, 0.5)' }},
                pointLabels: {{
                    color: '#94a3b8',
                    font: {{ size: 13, weight: '500' }},
                }},
            }},
        }},
        plugins: {{
            legend: {{ display: false }},
        }},
    }},
}});
</script>
</body>
</html>"""

    # ------------------------------------------------------------------
    # Sub-renderers
    # ------------------------------------------------------------------

    @staticmethod
    def _level_cn(level: str) -> str:
        mapping = {"green": "低风险", "yellow": "关注风险", "red": "高风险"}
        return mapping.get(level, level)

    @staticmethod
    def _dimensions_html(dims: list) -> str:
        rows = []
        for d in dims:
            border_class = f"border-l-{d.level}"
            raw_str = f"{d.raw_value:.1f}" if not hasattr(d.raw_value, "__float__") or (
                hasattr(d.raw_value, "__float__") and d.raw_value == d.raw_value
            ) else "N/A"
            if d.key == "litigation":
                raw_str = "是" if d.raw_value else "否"
            rows.append(f"""<div class="dim-item {border_class}">
    <div>
        <div class="dim-name">{d.name}</div>
        <div class="dim-detail">{d.detail}</div>
    </div>
    <div>
        <span class="dim-score">{d.score}</span>
        <span class="dim-detail">/100</span>
    </div>
</div>""")
        return "\n".join(rows)

    @staticmethod
    def _warnings_html(risk: RiskReport) -> str:
        if not risk.warnings:
            return ""
        items = "\n".join(
            f'<div class="warning-item"><span class="warning-icon">&#9888;</span><span>{w}</span></div>'
            for w in risk.warnings
        )
        return f'<div class="warnings">{items}</div>'

    @staticmethod
    def _sentiment_html(sentiment: Optional[SentimentReport]) -> str:
        if sentiment is None:
            return ""

        pos_count = sum(1 for it in sentiment.items if it.sentiment == "positive")
        neg_count = sum(1 for it in sentiment.items if it.sentiment == "negative")
        neu_count = sum(1 for it in sentiment.items if it.sentiment == "neutral")

        sentiment_emoji = {"positive": "&#128578; 正面",
                           "negative": "&#128577; 负面",
                           "neutral": "&#128528; 中性"}

        label = sentiment_emoji.get(sentiment.overall_label, "中性")

        # Timeline items (show up to 30)
        timeline_items = []
        for it in sentiment.items[:30]:
            dot_cls = {"positive": "dot-green", "negative": "dot-red",
                       "neutral": "dot-gray"}.get(it.sentiment, "dot-gray")
            timeline_items.append(f"""<div class="timeline-item">
    <span class="timeline-dot {dot_cls}"></span>
    <span class="timeline-date">{it.date}</span>
    <span class="timeline-title">{it.title}</span>
</div>""")

        # 预先拼接，避免 f-string 内不能包含反斜杠的语法限制
        timeline_html = "\n".join(timeline_items) if timeline_items else (
            '<div style="text-align:center;color:#64748b;padding:20px;">暂无新闻数据</div>'
        )

        return f"""
<div class="card" style="margin-top: 24px;">
    <h3>舆情监控</h3>
    <div class="summary-bar">
        <div class="summary-stat">
            <div class="stat-value" style="color: #f8fafc;">{len(sentiment.items)}</div>
            <div class="stat-label">总新闻数</div>
        </div>
        <div class="summary-stat">
            <div class="stat-value" style="color: #4ade80;">{pos_count}</div>
            <div class="stat-label">正面</div>
        </div>
        <div class="summary-stat">
            <div class="stat-value" style="color: #f87171;">{neg_count}</div>
            <div class="stat-label">负面</div>
        </div>
        <div class="summary-stat">
            <div class="stat-value" style="color: #64748b;">{neu_count}</div>
            <div class="stat-label">中性</div>
        </div>
        <div class="summary-stat">
            <div class="stat-value" style="color: #38bdf8;">{sentiment.overall_score}</div>
            <div class="stat-label">综合情绪分</div>
        </div>
    </div>
    <p style="color:#94a3b8;font-size:13px;text-align:center;margin-bottom:12px;">{label} | {sentiment.summary}</p>
    <div class="timeline">
        {timeline_html}
    </div>
</div>"""


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def generate_report(
    risk: RiskReport,
    sentiment: Optional[SentimentReport] = None,
    output_path: Optional[str] = None,
) -> str:
    """快捷生成函数"""
    gen = ReportGenerator()
    return gen.generate(risk, sentiment, output_path)
