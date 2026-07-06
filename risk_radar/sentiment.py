"""舆情监控 —— 基于新闻标题的情感分析和情绪评分"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentiment lexicon
# ---------------------------------------------------------------------------

POSITIVE_KEYWORDS = [
    # 业绩利好
    "增长", "上升", "新高", "突破", "利好", "分红", "回购", "增持",
    "盈利", "预增", "超预期", "中标", "签约", "获得订单", "投产",
    "研发成功", "获批", "上市", "涨停", "大涨", "走强", "创新高",
    "业绩亮眼", "扭亏为盈", "高增长", "需求旺盛", "订单饱满",
    # 政策利好
    "政策支持", "补贴", "减税", "扶持", "鼓励", "规划", "新基建",
    # 评级利好
    "买入", "增持评级", "目标价上调", "看好",
]

NEGATIVE_KEYWORDS = [
    # 业绩利空
    "下降", "下滑", "亏损", "预亏", "预减", "减值", "计提", "商誉",
    "退市", "跌停", "大跌", "暴跌", "下挫", "走弱", "创新低",
    "不及预期", "需求疲软", "产能过剩",
    # 风险事件
    "诉讼", "被执行", "失信", "立案调查", "监管函", "问询函",
    "处罚", "罚款", "整改", "停产", "事故", "召回", "调查",
    "减持", "质押", "爆仓", "平仓", "冻结",
    # 评级利空
    "卖出", "减持评级", "目标价下调", "看空",
    # 重大风险
    "强制退市", "暂停上市", "ST", "*ST", "破产", "重整",
]

# 强度修饰词 (加权)
INTENSIFIERS = {
    "大幅": 1.5,
    "持续": 1.3,
    "严重": 1.5,
    "重大": 1.4,
    "显著": 1.2,
    "剧烈": 1.5,
    "急剧": 1.5,
    "暴跌": 1.8,
    "暴涨": 1.8,
    "暴涨暴跌": 2.0,
}


@dataclass
class SentimentItem:
    """单条新闻的情感分析结果"""
    title: str
    date: str
    sentiment: str          # "positive" / "negative" / "neutral"
    score: float            # -5 ~ +5
    keywords: list[str] = field(default_factory=list)


@dataclass
class SentimentReport:
    """舆情分析报告"""
    ticker: str
    company_name: str
    items: list[SentimentItem] = field(default_factory=list)
    overall_score: float = 0.0          # -5 ~ +5
    overall_label: str = "neutral"       # positive / negative / neutral
    summary: str = ""
    timeline: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Sentiment analyzer
# ---------------------------------------------------------------------------

class SentimentMonitor:
    """舆情监控器 —— 基于 akshare 新闻数据"""

    @staticmethod
    def _fetch_news(ticker: str) -> Optional[pd.DataFrame]:
        """获取个股新闻"""
        try:
            import akshare as ak
            df = ak.stock_news_em(symbol=ticker)
            if df is None or df.empty:
                logger.warning("stock_news_em empty for %s", ticker)
            return df
        except Exception as exc:
            logger.warning("stock_news_em failed for %s: %s", ticker, exc)
            return None

    @staticmethod
    def _fetch_market_sentiment() -> Optional[pd.DataFrame]:
        """获取A股整体情绪指数"""
        try:
            import akshare as ak
            df = ak.index_news_sentiment_scope()
            return df
        except Exception as exc:
            logger.warning("index_news_sentiment_scope failed: %s", exc)
            return None

    @staticmethod
    def _analyze_title(title: str) -> tuple[str, float, list[str]]:
        """分析单条标题的情感倾向"""
        title_lower = title.lower()
        pos_count = 0
        neg_count = 0
        found_keywords: list[str] = []

        # 检查正向关键词
        for kw in POSITIVE_KEYWORDS:
            if kw in title_lower:
                pos_count += 1
                found_keywords.append(f"+{kw}")

        # 检查负向关键词
        for kw in NEGATIVE_KEYWORDS:
            if kw in title_lower:
                neg_count += 1
                found_keywords.append(f"-{kw}")

        # 强度加权
        weight = 1.0
        for intensifier, factor in INTENSIFIERS.items():
            if intensifier in title_lower:
                weight = max(weight, factor)

        # 计算原始分 (-5 ~ +5)
        raw = (pos_count - neg_count) * weight
        score = max(-5.0, min(5.0, raw))

        if score > 1.0:
            sentiment = "positive"
        elif score < -1.0:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return sentiment, score, found_keywords

    @staticmethod
    def _parse_date(date_val: Any) -> str:
        """解析新闻日期"""
        if date_val is None:
            return ""
        try:
            if isinstance(date_val, (datetime, pd.Timestamp)):
                return date_val.strftime("%Y-%m-%d")
            s = str(date_val).strip()
            # 尝试多种格式
            for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%m-%d", "%m/%d"):
                try:
                    return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
            # 尝试提取日期 (如 "2025-01-15 10:30:00")
            match = re.search(r"(\d{4}[-/]\d{2}[-/]\d{2})", s)
            if match:
                return match.group(1).replace("/", "-")
            return s[:10]
        except Exception:
            return str(date_val)[:10]

    def monitor(self, ticker: str, days: int = 30) -> SentimentReport:
        """执行舆情监控"""
        ticker = str(ticker).strip().zfill(6)

        # 获取公司名称
        company_name = self._get_company_name(ticker)

        # 获取新闻
        news_df = self._fetch_news(ticker)

        items: list[SentimentItem] = []

        if news_df is not None and not news_df.empty:
            # 定位标题列
            title_col = None
            date_col = None
            for col in news_df.columns:
                col_lower = str(col).lower()
                if title_col is None and ("标题" in col or "title" in col_lower or "新闻" in col):
                    title_col = col
                if date_col is None and ("时间" in col or "date" in col_lower or
                                          "发布时间" in col or "日期" in col):
                    date_col = col

            if title_col is None:
                # fallback: 使用第一列非数字列
                for col in news_df.columns:
                    if news_df[col].dtype == object:
                        title_col = col
                        break

            if title_col is None:
                logger.warning("No title column found in news data")
            else:
                for _, row in news_df.iterrows():
                    title = str(row.get(title_col, ""))
                    if not title or title == "nan":
                        continue
                    sent, score, kw = self._analyze_title(title)
                    date_str = self._parse_date(
                        row.get(date_col) if date_col else None
                    )
                    items.append(SentimentItem(
                        title=title,
                        date=date_str,
                        sentiment=sent,
                        score=score,
                        keywords=kw,
                    ))

        # 计算综合得分
        if items:
            overall_score = round(sum(it.score for it in items) / len(items), 2)
        else:
            overall_score = 0.0

        if overall_score > 0.5:
            overall_label = "positive"
        elif overall_score < -0.5:
            overall_label = "negative"
        else:
            overall_label = "neutral"

        # 生成摘要
        pos_count = sum(1 for it in items if it.sentiment == "positive")
        neg_count = sum(1 for it in items if it.sentiment == "negative")
        neu_count = sum(1 for it in items if it.sentiment == "neutral")

        summary = (
            f"近{days}日共获取{len(items)}条相关新闻: "
            f"正面{pos_count}条, 负面{neg_count}条, 中性{neu_count}条。"
            f"综合情绪: {self._label_cn(overall_label)}"
        )

        # 生成时间线 (按日期聚合)
        timeline = self._build_timeline(items)

        return SentimentReport(
            ticker=ticker,
            company_name=company_name,
            items=items,
            overall_score=overall_score,
            overall_label=overall_label,
            summary=summary,
            timeline=timeline,
        )

    @staticmethod
    def _build_timeline(items: list[SentimentItem]) -> list[dict[str, Any]]:
        """按日期聚合情绪"""
        daily: dict[str, list[float]] = {}
        for it in items:
            date_key = it.date if it.date else "未知"
            daily.setdefault(date_key, []).append(it.score)

        result = []
        for date_key in sorted(daily.keys()):
            scores = daily[date_key]
            avg = round(sum(scores) / len(scores), 2)
            result.append({"date": date_key, "score": avg, "count": len(scores)})
        return result

    @staticmethod
    def _label_cn(label: str) -> str:
        mapping = {"positive": "正面", "negative": "负面", "neutral": "中性"}
        return mapping.get(label, label)

    @staticmethod
    def _get_company_name(ticker: str) -> str:
        try:
            import akshare as ak
            info = ak.stock_individual_info_em(symbol=ticker)
            if info is not None:
                for _, row in info.iterrows():
                    if str(row.get("item", "")) == "股票简称":
                        return str(row.get("value", ticker))
        except Exception:
            pass
        return ticker


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def monitor_ticker(ticker: str) -> SentimentReport:
    """快捷监控函数"""
    monitor = SentimentMonitor()
    return monitor.monitor(ticker)
