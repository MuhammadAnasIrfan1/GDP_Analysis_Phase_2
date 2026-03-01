from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from core.contracts import DataSink, Record


class ConsoleWriter(DataSink):
    """
    Simple sink that prints results to the console in a human-readable form.
    """

    def write(self, records: List[Record]) -> None:
        for record in records:
            metric = record.get("metric", "unknown")
            print(f"\n=== {metric.replace('_', ' ').upper()} ===")
            self._print_metric(record)

    def _print_metric(self, record: Dict[str, Any]) -> None:
        metric = record.get("metric")
        if metric in {
            "top_10_countries_by_gdp",
            "bottom_10_countries_by_gdp",
        }:
            countries = record.get("countries", [])
            for idx, item in enumerate(countries, start=1):
                country = item.get("country")
                gdp = item.get("gdp")
                print(f"{idx:2d}. {country:40s} {gdp:,.0f}")
        elif metric == "gdp_growth_by_country":
            for item in record.get("countries", []):
                country = item.get("country")
                growth = item.get("growth_rate", 0.0) * 100.0
                print(f"{country:40s} {growth:8.2f}%")
        elif metric == "average_gdp_by_continent":
            for item in record.get("continents", []):
                name = item.get("continent")
                avg = item.get("average_gdp", 0.0)
                print(f"{name:20s} {avg:,.0f}")
        elif metric == "global_gdp_trend":
            for point in record.get("trend", []):
                year = point.get("year")
                total = point.get("global_gdp", 0.0)
                print(f"{year}: {total:,.0f}")
        elif metric == "fastest_growing_continent":
            fastest = record.get("result")
            if not fastest:
                print("No data available.")
                return
            name = fastest.get("continent")
            growth = fastest.get("growth_rate", 0.0) * 100.0
            print(f"{name} ({growth:.2f}% growth)")
        elif metric == "consistent_gdp_decline":
            years = record.get("years", [])
            print(f"Years window: {years}")
            for item in record.get("countries", []):
                country = item.get("country")
                print(f"- {country}")
        elif metric == "continent_contribution_to_global_gdp":
            for item in record.get("continents", []):
                name = item.get("continent")
                share = item.get("share_of_global_gdp", 0.0) * 100.0
                print(f"{name:20s} {share:6.2f}%")
        else:
            # Fallback: just pretty-print the dict.
            for key, value in record.items():
                print(f"{key}: {value}")


class GraphicsChartWriter(DataSink):
    """
    Sink that generates simple chart images for selected metrics.

    Uses matplotlib if available; otherwise, it degrades gracefully by
    emitting a message and skipping chart generation.
    """

    def __init__(self, output_dir: str = "charts") -> None:
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def write(self, records: List[Record]) -> None:
        try:
            import matplotlib.pyplot as plt  # type: ignore[import]
        except Exception:  # pragma: no cover - optional dependency
            print(
                "matplotlib is not available; GraphicsChartWriter "
                "will not generate charts."
            )
            return

        for record in records:
            metric = record.get("metric")
            if metric == "global_gdp_trend":
                self._plot_global_trend(record, plt)
            elif metric == "continent_contribution_to_global_gdp":
                self._plot_continent_contribution(record, plt)
            elif metric in {
                "top_10_countries_by_gdp",
                "bottom_10_countries_by_gdp",
            }:
                self._plot_top_bottom(record, plt)
            elif metric == "gdp_growth_by_country":
                self._plot_growth_by_country(record, plt)
            elif metric == "average_gdp_by_continent":
                self._plot_average_gdp_by_continent(record, plt)
            elif metric == "fastest_growing_continent":
                self._plot_fastest_growing_continent(record, plt)

    def _plot_global_trend(self, record: Dict[str, Any], plt: Any) -> None:
        trend = record.get("trend", [])
        if not trend:
            return
        years = [point["year"] for point in trend]
        totals = [point["global_gdp"] for point in trend]
        fig, ax = plt.subplots()
        ax.plot(years, totals, marker="o")
        ax.set_title("Global GDP Trend")
        ax.set_xlabel("Year")
        ax.set_ylabel("GDP (current US$)")
        fig.tight_layout()
        path = self._output_dir / "global_gdp_trend.png"
        fig.savefig(path)
        plt.close(fig)
        print(f"Saved chart: {path}")

    def _plot_continent_contribution(self, record: Dict[str, Any], plt: Any) -> None:
        continents = record.get("continents", [])
        if not continents:
            return
        labels = [item["continent"] for item in continents]
        shares = [item["share_of_global_gdp"] for item in continents]
        fig, ax = plt.subplots()
        ax.bar(labels, shares)
        ax.set_title("Continent Contribution to Global GDP")
        ax.set_ylabel("Share of Global GDP")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        fig.tight_layout()
        path = self._output_dir / "continent_contribution.png"
        fig.savefig(path)
        plt.close(fig)
        print(f"Saved chart: {path}")

    def _plot_top_bottom(self, record: Dict[str, Any], plt: Any) -> None:
        countries = record.get("countries", [])
        if not countries:
            return
        labels = [c["country"] for c in countries]
        values = [c["gdp"] for c in countries]
        fig, ax = plt.subplots()
        ax.bar(range(len(labels)), values)
        ax.set_title(record.get("metric", "").replace("_", " ").title())
        ax.set_ylabel("GDP (current US$)")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        fig.tight_layout()
        filename = f"{record.get('metric', 'top_bottom')}.png"
        path = self._output_dir / filename
        fig.savefig(path)
        plt.close(fig)
        print(f"Saved chart: {path}")

    def _plot_growth_by_country(self, record: Dict[str, Any], plt: Any) -> None:
        countries = record.get("countries", [])
        if not countries:
            return
        labels = [c["country"] for c in countries]
        values = [c["growth_rate"] * 100.0 for c in countries]
        fig, ax = plt.subplots()
        ax.bar(range(len(labels)), values)
        ax.set_title("GDP Growth Rate by Country")
        ax.set_ylabel("Growth rate (%)")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=90, ha="right")
        fig.tight_layout()
        path = self._output_dir / "gdp_growth_by_country.png"
        fig.savefig(path)
        plt.close(fig)
        print(f"Saved chart: {path}")

    def _plot_average_gdp_by_continent(
        self, record: Dict[str, Any], plt: Any
    ) -> None:
        continents = record.get("continents", [])
        if not continents:
            return
        labels = [c["continent"] for c in continents]
        values = [c["average_gdp"] for c in continents]
        fig, ax = plt.subplots()
        ax.bar(range(len(labels)), values)
        ax.set_title("Average GDP by Continent")
        ax.set_ylabel("Average GDP (current US$)")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        fig.tight_layout()
        path = self._output_dir / "average_gdp_by_continent.png"
        fig.savefig(path)
        plt.close(fig)
        print(f"Saved chart: {path}")

    def _plot_fastest_growing_continent(
        self, record: Dict[str, Any], plt: Any
    ) -> None:
        fastest = record.get("result")
        if not fastest:
            return
        label = fastest.get("continent")
        value = fastest.get("growth_rate", 0.0) * 100.0
        fig, ax = plt.subplots()
        ax.bar([label], [value])
        ax.set_title("Fastest Growing Continent")
        ax.set_ylabel("Growth rate (%)")
        fig.tight_layout()
        path = self._output_dir / "fastest_growing_continent.png"
        fig.savefig(path)
        plt.close(fig)
        print(f"Saved chart: {path}")

