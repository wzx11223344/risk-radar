#!/usr/bin/env python3
"""Risk Radar CLI -- 企业风险评估与舆情监控命令行工具

用法:
    python radar.py scan --ticker 600519          # 扫描单只股票风险
    python radar.py scan --ticker 000858 --output report.html  # 输出HTML报告
    python radar.py monitor --ticker 600519        # 只看舆情监控
    python radar.py batch --tickers 600519,000858  # 批量扫描
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime

import click

# ---------------------------------------------------------------------------
# Rich 表格 (可选, 无依赖时降级为纯文本)
# ---------------------------------------------------------------------------
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    HAS_RICH = True
    console = Console()
except ImportError:
    HAS_RICH = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _level_color(level: str) -> str:
    mapping = {"green": "green", "yellow": "yellow", "red": "red"}
    return mapping.get(level, "white")


def _level_cn(level: str) -> str:
    mapping = {"green": "低风险", "yellow": "关注风险", "red": "高风险"}
    return mapping.get(level, level)


def _level_icon(level: str) -> str:
    mapping = {"green": "\u2705", "yellow": "\u26a0\ufe0f", "red": "\u274c"}
    return mapping.get(level, "?")


# ---------------------------------------------------------------------------
# CLI groups
# ---------------------------------------------------------------------------

@click.group()
@click.option("--verbose", "-v", is_flag=True, help="显示详细日志")
@click.pass_context
def cli(ctx, verbose):
    """Risk Radar -- 企业风险雷达: 基于真实财报数据的风险评估与舆情监控工具"""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    _setup_logging(verbose)


# -- scan ----------------------------------------------------------------

@cli.command()
@click.option("--ticker", "-t", required=True, help="股票代码, 如 600519")
@click.option("--output", "-o", default=None, help="输出HTML报告路径 (可选)")
@click.option("--no-sentiment", is_flag=True, help="跳过舆情分析")
@click.pass_context
def scan(ctx, ticker, output, no_sentiment):
    """对指定股票执行全面风险扫描 (含舆情)"""
    from risk_radar.scanner import RiskScanner
    from risk_radar.sentiment import SentimentMonitor
    from risk_radar.report import ReportGenerator

    ticker = str(ticker).strip().zfill(6)

    if HAS_RICH:
        console.print(Panel(f"[bold cyan]Risk Radar[/bold cyan] - 企业风险扫描",
                            subtitle=f"ticker={ticker}"))
        console.print("[dim]正在获取财报数据...[/dim]")
    else:
        click.echo(f"Risk Radar - 扫描 {ticker} ...")

    # 1. 风险扫描
    scanner = RiskScanner()
    risk_report = scanner.scan(ticker)

    # 2. 舆情监控
    sentiment_report = None
    if not no_sentiment:
        if HAS_RICH:
            console.print("[dim]正在获取舆情数据...[/dim]")
        else:
            click.echo("正在获取舆情数据...")
        monitor = SentimentMonitor()
        sentiment_report = monitor.monitor(ticker)

    # 3. 终端展示
    _print_risk_report(risk_report)
    if sentiment_report:
        _print_sentiment_report(sentiment_report)

    # 4. HTML 输出
    if output:
        ReportGenerator().generate(risk_report, sentiment_report, output)
        if HAS_RICH:
            console.print(f"\n[green]HTML 报告已保存至: {output}[/green]")
        else:
            click.echo(f"\nHTML 报告已保存至: {output}")
    else:
        # 默认保存到当前目录
        default_path = f"risk_radar_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        ReportGenerator().generate(risk_report, sentiment_report, default_path)
        if HAS_RICH:
            console.print(f"\n[green]HTML 报告已保存至: {default_path}[/green]")
        else:
            click.echo(f"\nHTML 报告已保存至: {default_path}")


# -- monitor -------------------------------------------------------------

@cli.command()
@click.option("--ticker", "-t", required=True, help="股票代码, 如 000858")
@click.option("--days", "-d", default=30, help="监控天数 (默认30)")
@click.pass_context
def monitor(ctx, ticker, days):
    """对指定股票进行舆情监控"""
    from risk_radar.sentiment import SentimentMonitor

    ticker = str(ticker).strip().zfill(6)

    if HAS_RICH:
        console.print(Panel(f"[bold cyan]Risk Radar[/bold cyan] - 舆情监控",
                            subtitle=f"ticker={ticker}, days={days}"))
    else:
        click.echo(f"Risk Radar - 舆情监控 {ticker} (近{days}天)")

    monitor_obj = SentimentMonitor()
    report = monitor_obj.monitor(ticker, days=days)
    _print_sentiment_report(report)


# -- batch ---------------------------------------------------------------

@cli.command()
@click.option("--tickers", "-t", required=True,
              help="逗号分隔的股票代码列表, 如 600519,000858,601318")
@click.option("--output", "-o", default=None,
              help="输出汇总CSV路径 (可选)")
@click.pass_context
def batch(ctx, tickers, output):
    """批量扫描多只股票的风险评分"""
    from risk_radar.scanner import RiskScanner

    scanner = RiskScanner()
    codes = [c.strip().zfill(6) for c in tickers.split(",")]

    results = []
    for code in codes:
        try:
            report = scanner.scan(code)
            results.append({
                "ticker": report.ticker,
                "name": report.company_name,
                "overall_score": report.overall_score,
                "level": report.overall_level,
                "warnings": len(report.warnings),
            })
        except Exception as exc:
            results.append({
                "ticker": code,
                "name": "ERROR",
                "overall_score": 0,
                "level": "red",
                "warnings": 0,
                "error": str(exc),
            })

    # 按综合评分排序 (低分在前 = 高风险在前)
    results.sort(key=lambda r: r["overall_score"])

    # 展示
    if HAS_RICH:
        table = Table(title="批量扫描结果", title_style="bold cyan")
        table.add_column("代码", style="dim")
        table.add_column("名称")
        table.add_column("评分", justify="right")
        table.add_column("等级")
        table.add_column("警告数", justify="right")
        for r in results:
            level_color = _level_color(r["level"])
            table.add_row(
                r["ticker"], r["name"],
                str(r["overall_score"]),
                f"[{level_color}]{_level_cn(r['level'])}[/{level_color}]",
                str(r["warnings"]),
            )
        console.print(table)
    else:
        click.echo(f"{'代码':<10} {'名称':<10} {'评分':>6} {'等级'}")
        click.echo("-" * 40)
        for r in results:
            click.echo(f"{r['ticker']:<10} {r['name']:<10} "
                       f"{r['overall_score']:>6} {_level_cn(r['level'])}")

    # 输出CSV
    if output:
        import csv
        with open(output, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["ticker", "name",
                                                    "overall_score", "level", "warnings"])
            writer.writeheader()
            writer.writerows(results)
        if HAS_RICH:
            console.print(f"\n[green]CSV 已保存至: {output}[/green]")
        else:
            click.echo(f"\nCSV 已保存至: {output}")


# ---------------------------------------------------------------------------
# Print helpers
# ---------------------------------------------------------------------------

def _print_risk_report(report):
    """终端打印风险报告"""
    if HAS_RICH:
        # Overall
        level_color = _level_color(report.overall_level)
        console.print(f"\n[bold]{report.company_name} ({report.ticker})[/bold]")
        console.print(f"综合评分: [{level_color}]{report.overall_score}/100"
                      f" - {_level_cn(report.overall_level)}[/{level_color}]")

        # Dimensions table
        table = Table(title="六维风险指标")
        table.add_column("维度", style="bold")
        table.add_column("原始值", justify="right")
        table.add_column("评分", justify="right")
        table.add_column("等级")

        for d in report.dimensions:
            lc = _level_color(d.level)
            raw = d.raw_value
            if d.key == "litigation":
                raw_str = "是" if raw else "否"
                raw_str = f"{raw_str}" if isinstance(raw, (int, float)) else str(raw)
            else:
                try:
                    raw_str = f"{float(raw):.1f}"
                except (TypeError, ValueError):
                    raw_str = "N/A"
            table.add_row(d.name, raw_str, str(d.score),
                          f"[{lc}]{_level_icon(d.level)} {d.detail[:40]}[/{lc}]")
        console.print(table)

        # Warnings
        if report.warnings:
            console.print("\n[bold red]风险警告:[/bold red]")
            for w in report.warnings:
                console.print(f"  [red]\u2716[/red] {w}")
    else:
        click.echo(f"\n{report.company_name} ({report.ticker})")
        click.echo(f"综合评分: {report.overall_score}/100 - {_level_cn(report.overall_level)}")
        click.echo(f"\n{'维度':<12} {'原始值':>10} {'评分':>6} {'等级'}")
        click.echo("-" * 50)
        for d in report.dimensions:
            try:
                raw_str = f"{float(d.raw_value):.1f}"
            except (TypeError, ValueError):
                raw_str = str(d.raw_value)[:10]
            if d.key == "litigation":
                raw_str = "是" if d.raw_value else "否"
            click.echo(f"{d.name:<12} {raw_str:>10} {d.score:>6} {_level_cn(d.level)}")
        if report.warnings:
            click.echo(f"\n风险警告 ({len(report.warnings)}):")
            for w in report.warnings:
                click.echo(f"  - {w}")


def _print_sentiment_report(report):
    """终端打印舆情报告"""
    if HAS_RICH:
        pos = sum(1 for it in report.items if it.sentiment == "positive")
        neg = sum(1 for it in report.items if it.sentiment == "negative")
        neu = sum(1 for it in report.items if it.sentiment == "neutral")

        console.print(f"\n[bold]舆情分析: {report.company_name}[/bold]")
        console.print(f"综合情绪分: {report.overall_score} "
                      f"({_sent_label_cn(report.overall_label)})")
        console.print(f"新闻总数: {len(report.items)} "
                      f"[green]\u25b2{pos}[/green] "
                      f"[red]\u25bc{neg}[/red] "
                      f"[dim]\u25cb{neu}[/dim]")
        console.print(report.summary)

        # 展示最近10条
        if report.items:
            console.print("\n[bold]最近新闻:[/bold]")
            for it in report.items[:10]:
                icon = {"positive": "[green]+[/green]",
                        "negative": "[red]-[/red]",
                        "neutral": "[dim]~[/dim]"}.get(it.sentiment, " ")
                console.print(f"  {icon} [{dim}{it.date}[/dim]] {it.title[:60]}")
    else:
        click.echo(f"\n舆情分析: {report.company_name}")
        click.echo(f"综合情绪分: {report.overall_score} ({_sent_label_cn(report.overall_label)})")
        click.echo(report.summary)
        if report.items:
            click.echo("\n最近新闻:")
            for it in report.items[:10]:
                click.echo(f"  [{it.sentiment[0].upper()}] {it.date} {it.title[:60]}")


def _sent_label_cn(label: str) -> str:
    mapping = {"positive": "正面", "negative": "负面", "neutral": "中性"}
    return mapping.get(label, label)


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
