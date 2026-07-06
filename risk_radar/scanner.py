"""风险扫描器 —— 从真实财报数据计算企业风险指标并评分"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class RiskDimension:
    """单个风险维度"""
    name: str                # 维度名称 (中文)
    key: str                 # 维度键名
    raw_value: float         # 原始数值
    score: int               # 0-100 评分 (越低风险越高)
    level: str               # "green" / "yellow" / "red"
    detail: str = ""         # 补充说明


@dataclass
class RiskReport:
    """扫描结果汇总"""
    ticker: str
    company_name: str
    dimensions: list[RiskDimension] = field(default_factory=list)
    overall_score: int = 0
    overall_level: str = "green"
    warnings: list[str] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Risk scoring helpers
# ---------------------------------------------------------------------------

def _score_debt_ratio(value: float) -> tuple[int, str, str]:
    """资产负债率: 越低越好，>70% 高风险"""
    if pd.isna(value):
        return (50, "yellow", "数据缺失")
    if value > 85:
        return (10, "red", f"极高负债 {value:.1f}%，偿债压力大")
    if value > 70:
        return (30, "red", f"高负债 {value:.1f}%，超过警戒线")
    if value > 55:
        return (60, "yellow", f"中等负债 {value:.1f}%")
    if value > 40:
        return (80, "green", f"合理负债 {value:.1f}%")
    return (95, "green", f"低负债 {value:.1f}%，财务稳健")


def _score_cash_flow_ratio(value: float) -> tuple[int, str, str]:
    """现金流覆盖比率 (经营现金流/流动负债): 越高越好"""
    if pd.isna(value):
        return (50, "yellow", "数据缺失")
    if value < 0:
        return (10, "red", f"现金流为负 {value:.2f}，经营造血不足")
    if value < 0.2:
        return (25, "red", f"现金流覆盖不足 {value:.2f}")
    if value < 0.5:
        return (55, "yellow", f"现金流一般 {value:.2f}")
    if value < 1.0:
        return (75, "green", f"现金流良好 {value:.2f}")
    return (95, "green", f"现金流充裕 {value:.2f}")


def _score_pledge_ratio(value: float) -> tuple[int, str, str]:
    """股权质押比例: 越低越好，>40% 高风险"""
    if pd.isna(value):
        return (70, "yellow", "未检测到明显质押或无数据")
    if value > 60:
        return (10, "red", f"质押比例极高 {value:.1f}%，控制权风险大")
    if value > 40:
        return (30, "red", f"高质押 {value:.1f}%，关注平仓风险")
    if value > 20:
        return (60, "yellow", f"中等质押 {value:.1f}%")
    if value > 10:
        return (80, "green", f"低质押 {value:.1f}%")
    return (95, "green", f"质押极低 {value:.1f}% 或无质押")


def _score_goodwill_ratio(value: float) -> tuple[int, str, str]:
    """商誉占净资产比: 越低越好，>30% 高风险"""
    if pd.isna(value):
        return (70, "yellow", "未检测到商誉数据")
    if value > 50:
        return (10, "red", f"商誉占比极高 {value:.1f}%，减值风险大")
    if value > 30:
        return (30, "red", f"高商誉 {value:.1f}%，关注减值")
    if value > 15:
        return (60, "yellow", f"商誉偏高 {value:.1f}%")
    if value > 5:
        return (80, "green", f"商誉可控 {value:.1f}%")
    return (95, "green", f"商誉极低 {value:.1f}%")


def _score_litigation(has_litigation: bool) -> tuple[int, str, str]:
    """诉讼风险标记: 有则为高风险"""
    if has_litigation:
        return (20, "red", "检测到重大诉讼/被执行记录")
    return (90, "green", "未检测到重大诉讼风险")


def _score_profitability(net_margin: float) -> tuple[int, str, str]:
    """盈利能力 (净利率): 越高越好"""
    if pd.isna(net_margin):
        return (50, "yellow", "数据缺失")
    if net_margin < 0:
        return (10, "red", f"净利润为负 {net_margin:.1f}%，持续亏损风险")
    if net_margin < 5:
        return (40, "yellow", f"利润率偏低 {net_margin:.1f}%")
    if net_margin < 15:
        return (70, "green", f"利润率良好 {net_margin:.1f}%")
    return (90, "green", f"高利润率 {net_margin:.1f}%")


def _traffic_light(score: int) -> str:
    if score >= 70:
        return "green"
    if score >= 40:
        return "yellow"
    return "red"


# ---------------------------------------------------------------------------
# Main scanner class
# ---------------------------------------------------------------------------

class RiskScanner:
    """企业风险扫描器 -- 基于 akshare 真实财报数据"""

    DIMENSION_KEYS = [
        "debt_ratio",
        "cash_flow",
        "pledge",
        "goodwill",
        "litigation",
        "profitability",
    ]

    DIMENSION_LABELS = {
        "debt_ratio": "资产负债率",
        "cash_flow": "现金流覆盖",
        "pledge": "股权质押",
        "goodwill": "商誉占比",
        "litigation": "诉讼风险",
        "profitability": "盈利能力",
    }

    # ------------------------------------------------------------------
    # Data fetching (all via akshare)
    # ------------------------------------------------------------------

    @staticmethod
    def _fetch_financial_abstract(ticker: str) -> Optional[pd.DataFrame]:
        """获取同花顺财务摘要数据 (最近一期)"""
        try:
            import akshare as ak
            df = ak.stock_financial_abstract_ths(symbol=ticker, indicator="按报告期")
            if df is None or df.empty:
                logger.warning("stock_financial_abstract_ths returned empty for %s", ticker)
                return None
            return df
        except Exception as exc:
            logger.warning("stock_financial_abstract_ths failed for %s: %s", ticker, exc)
            return None

    @staticmethod
    def _fetch_financial_indicator(ticker: str) -> Optional[pd.DataFrame]:
        """获取财务分析指标"""
        try:
            import akshare as ak
            df = ak.stock_financial_analysis_indicator(symbol=ticker)
            if df is None or df.empty:
                logger.warning("stock_financial_analysis_indicator empty for %s", ticker)
                return None
            return df
        except Exception as exc:
            logger.warning("stock_financial_analysis_indicator failed for %s: %s", ticker, exc)
            return None

    @staticmethod
    def _fetch_pledge_detail(ticker: str) -> Optional[pd.DataFrame]:
        """获取股权质押明细"""
        try:
            import akshare as ak
            df = ak.stock_em_gpzy_pledge_ratio_detail()
            if df is None or df.empty:
                logger.warning("stock_em_gpzy_pledge_ratio_detail empty")
                return None
            # 按股票代码筛选
            code_str = str(ticker)
            matched = df[df["股票代码"].astype(str).str.strip() == code_str]
            if matched.empty:
                logger.warning("No pledge data for ticker %s", ticker)
                return None
            return matched
        except Exception as exc:
            logger.warning("stock_em_gpzy_pledge_ratio_detail failed: %s", exc)
            return None

    @staticmethod
    def _fetch_stock_info(ticker: str) -> Optional[pd.DataFrame]:
        """获取个股基本信息"""
        try:
            import akshare as ak
            df = ak.stock_individual_info_em(symbol=ticker)
            if df is None or df.empty:
                return None
            return df
        except Exception as exc:
            logger.warning("stock_individual_info_em failed for %s: %s", ticker, exc)
            return None

    @staticmethod
    def _check_litigation(ticker: str) -> bool:
        """检查是否有诉讼/被执行风险 (基于公开信息)"""
        try:
            import akshare as ak

            # 尝试用新闻数据检测诉讼关键词
            df_news = ak.stock_news_em(symbol=ticker)
            if df_news is None or df_news.empty:
                return False

            keywords = ["诉讼", "被执行", "强制执行", "失信", "立案",
                        "仲裁", "违规", "处罚", "ST", "*ST", "退市风险",
                        "监管函", "问询函", "立案调查"]
            text_col = None
            for col_candidate in ["新闻标题", "标题", "title", "content", "内容"]:
                if col_candidate in df_news.columns:
                    text_col = col_candidate
                    break

            if text_col is None:
                return False

            combined = " ".join(df_news[text_col].astype(str).tolist())
            for kw in keywords:
                if kw in combined:
                    logger.info("Litigation keyword '%s' found for %s", kw, ticker)
                    return True
            return False
        except Exception as exc:
            logger.warning("Litigation check failed for %s: %s", ticker, exc)
            return False

    # ------------------------------------------------------------------
    # Risk computation
    # ------------------------------------------------------------------

    def scan(self, ticker: str) -> RiskReport:
        """对指定股票执行全面风险扫描, 返回 RiskReport"""
        # 清理 ticker
        ticker = str(ticker).strip().zfill(6)

        # 获取公司名称
        company_name = self._get_company_name(ticker)

        # 获取原始数据
        fa_df = self._fetch_financial_abstract(ticker)
        fi_df = self._fetch_financial_indicator(ticker)
        pledge_df = self._fetch_pledge_detail(ticker)
        has_litigation = self._check_litigation(ticker)

        # 提取各指标
        debt_ratio = self._extract_debt_ratio(fa_df)
        cash_flow = self._extract_cash_flow(fi_df)
        pledge = self._extract_pledge_ratio(pledge_df)
        goodwill = self._extract_goodwill_ratio(fa_df)
        net_margin = self._extract_net_margin(fi_df)

        # 评分
        dims: list[RiskDimension] = []

        s, lvl, det = _score_debt_ratio(debt_ratio)
        dims.append(RiskDimension("资产负债率", "debt_ratio", debt_ratio, s, lvl, det))

        s, lvl, det = _score_cash_flow_ratio(cash_flow)
        dims.append(RiskDimension("现金流覆盖", "cash_flow", cash_flow, s, lvl, det))

        s, lvl, det = _score_pledge_ratio(pledge)
        dims.append(RiskDimension("股权质押", "pledge", pledge, s, lvl, det))

        s, lvl, det = _score_goodwill_ratio(goodwill)
        dims.append(RiskDimension("商誉占比", "goodwill", goodwill, s, lvl, det))

        s, lvl, det = _score_litigation(has_litigation)
        dims.append(RiskDimension("诉讼风险", "litigation",
                                  float(has_litigation), s, lvl, det))

        s, lvl, det = _score_profitability(net_margin)
        dims.append(RiskDimension("盈利能力", "profitability", net_margin, s, lvl, det))

        # 综合评分 (加权平均)
        weights = {
            "debt_ratio": 0.20,
            "cash_flow": 0.20,
            "pledge": 0.15,
            "goodwill": 0.15,
            "litigation": 0.15,
            "profitability": 0.15,
        }
        overall = round(
            sum(d.score * weights.get(d.key, 0.1) for d in dims)
        )
        overall_level = _traffic_light(overall)

        # 收集警告
        warnings = [d.detail for d in dims if d.level == "red"]

        return RiskReport(
            ticker=ticker,
            company_name=company_name,
            dimensions=dims,
            overall_score=overall,
            overall_level=overall_level,
            warnings=warnings,
            raw_data={
                "debt_ratio": debt_ratio,
                "cash_flow": cash_flow,
                "pledge": pledge,
                "goodwill": goodwill,
                "net_margin": net_margin,
                "has_litigation": has_litigation,
            },
        )

    # ------------------------------------------------------------------
    # Data extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_company_name(ticker: str) -> str:
        try:
            info = RiskScanner._fetch_stock_info(ticker)
            if info is not None:
                for _, row in info.iterrows():
                    if str(row.get("item", "")) == "股票简称":
                        return str(row.get("value", ticker))
        except Exception:
            pass
        return ticker

    @staticmethod
    def _extract_debt_ratio(fa_df: Optional[pd.DataFrame]) -> float:
        """从财务摘要中提取资产负债率(%)"""
        if fa_df is None:
            return float("nan")
        try:
            # fa_df 第一列是指标名称, 其他列是各报告期数据
            col = fa_df.columns[0]
            for _, row in fa_df.iterrows():
                if "资产负债率" in str(row[col]):
                    # 取最近一期有效数值
                    for c in fa_df.columns[1:]:
                        val = row[c]
                        if pd.notna(val) and val not in ("--", "", None):
                            return float(val)
            logger.warning("Debt ratio not found in financial abstract")
        except Exception as exc:
            logger.warning("Failed to extract debt ratio: %s", exc)
        return float("nan")

    @staticmethod
    def _extract_cash_flow(fi_df: Optional[pd.DataFrame]) -> float:
        """从财务指标中提取经营现金流/流动负债"""
        if fi_df is None:
            return float("nan")
        try:
            # 尝试找到"现金流量比率" 或 "经营现金流/负债"
            col = fi_df.columns[0]
            for _, row in fi_df.iterrows():
                key = str(row[col])
                if "现金流量比率" in key or "现金流" in key:
                    for c in fi_df.columns[1:]:
                        val = row[c]
                        if pd.notna(val) and val not in ("--", "", None):
                            # 比率通常以%表示, 转换为小数
                            v = float(val)
                            if abs(v) > 10:  # 百分比形式
                                return v / 100.0
                            return v
            logger.warning("Cash flow ratio not found")
        except Exception as exc:
            logger.warning("Failed to extract cash flow: %s", exc)
        return float("nan")

    @staticmethod
    def _extract_pledge_ratio(pledge_df: Optional[pd.DataFrame]) -> float:
        """提取股权质押比例(%)"""
        if pledge_df is None:
            return float("nan")
        try:
            # 寻找"质押比例"列
            for col in pledge_df.columns:
                if "质押" in str(col) and ("比例" in str(col) or "比率" in str(col)):
                    vals = pd.to_numeric(pledge_df[col], errors="coerce")
                    if vals.notna().any():
                        return float(vals.dropna().iloc[0])
            logger.warning("Pledge ratio column not found")
        except Exception as exc:
            logger.warning("Failed to extract pledge ratio: %s", exc)
        return float("nan")

    @staticmethod
    def _extract_goodwill_ratio(fa_df: Optional[pd.DataFrame]) -> float:
        """从财务摘要中提取商誉占净资产比例(%)"""
        if fa_df is None:
            return float("nan")
        try:
            col = fa_df.columns[0]
            goodwill_val = None
            equity_val = None
            for _, row in fa_df.iterrows():
                key = str(row[col])
                if "商誉" in key:
                    for c in fa_df.columns[1:]:
                        v = row[c]
                        if pd.notna(v) and v not in ("--", "", None):
                            goodwill_val = float(v)
                            break
                if "净资产" in key or "股东权益" in key or "归属母公司股东权益" in key:
                    for c in fa_df.columns[1:]:
                        v = row[c]
                        if pd.notna(v) and v not in ("--", "", None):
                            equity_val = float(v)
                            # 净资产可能以亿元为单位, 需要对齐商誉的单位
                            if equity_val < abs(goodwill_val or 0) / 100:
                                equity_val *= 1e8
                            break
            if goodwill_val is not None and equity_val is not None and equity_val > 0:
                return (goodwill_val / equity_val) * 100.0
            logger.warning("Goodwill or equity data missing")
        except Exception as exc:
            logger.warning("Failed to extract goodwill ratio: %s", exc)
        return float("nan")

    @staticmethod
    def _extract_net_margin(fi_df: Optional[pd.DataFrame]) -> float:
        """从财务指标中提取净利率(%)"""
        if fi_df is None:
            return float("nan")
        try:
            col = fi_df.columns[0]
            for _, row in fi_df.iterrows():
                key = str(row[col])
                if "净利率" in key or "销售净利率" in key:
                    for c in fi_df.columns[1:]:
                        val = row[c]
                        if pd.notna(val) and val not in ("--", "", None):
                            return float(val)
            logger.warning("Net margin not found")
        except Exception as exc:
            logger.warning("Failed to extract net margin: %s", exc)
        return float("nan")


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def scan_ticker(ticker: str) -> RiskReport:
    """快捷扫描函数"""
    scanner = RiskScanner()
    return scanner.scan(ticker)
