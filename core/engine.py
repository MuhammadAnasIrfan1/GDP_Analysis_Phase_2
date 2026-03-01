from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from .contracts import DataSink, PipelineService, Record


@dataclass(frozen=True)
class EngineConfig:
    continent: str
    year: int
    start_year: int
    end_year: int
    decline_years: int = 3


class TransformationEngine(PipelineService):
    """
    Core transformation engine.

    This class is completely agnostic of input and output details.
    A concrete DataSink is injected via the constructor, and inputs
    interact with it only through the PipelineService protocol.
    """

    def __init__(self, sink: DataSink, config: EngineConfig) -> None:
        self._sink = sink
        self._config = config

    # PipelineService API -------------------------------------------------
    def execute(self, raw_data: List[Any]) -> None:
        """
        Entry point used by Input drivers.
        raw_data is typically a list of GDP records loaded from an external source.
        """
        records = self._ensure_record_shape(raw_data)

        results: List[Record] = []
        results.extend(self._top_bottom_gdp(records))
        results.extend(self._gdp_growth_by_country(records))
        results.extend(self._average_gdp_by_continent(records))
        results.extend(self._global_gdp_trend(records))
        results.extend(self._fastest_growing_continent(records))
        results.extend(self._consistent_decline_countries(records))
        results.extend(self._continent_contribution(records))

        self._sink.write(results)

    # Internal helpers ----------------------------------------------------
    def _ensure_record_shape(self, raw_data: Iterable[Any]) -> List[Record]:
        records: List[Record] = []
        for item in raw_data:
            if isinstance(item, dict):
                records.append(item)
        return records

    # Metric 1 & 2: top / bottom 10 --------------------------------------
    def _top_bottom_gdp(self, records: List[Record]) -> List[Record]:
        continent = self._config.continent
        year_key = str(self._config.year)

        filtered: List[Tuple[str, float]] = []
        for rec in records:
            if rec.get("Continent") != continent:
                continue
            value = rec.get(year_key)
            if value is None:
                continue
            try:
                gdp = float(value)
            except (TypeError, ValueError):
                continue
            filtered.append((str(rec.get("Country Name", "")), gdp))

        filtered.sort(key=lambda x: x[1])

        bottom = filtered[:10]
        top = list(reversed(filtered[-10:])) if filtered else []

        return [
            {
                "metric": "top_10_countries_by_gdp",
                "continent": continent,
                "year": self._config.year,
                "countries": [{"country": c, "gdp": g} for c, g in top],
            },
            {
                "metric": "bottom_10_countries_by_gdp",
                "continent": continent,
                "year": self._config.year,
                "countries": [{"country": c, "gdp": g} for c, g in bottom],
            },
        ]

    # Metric 3: GDP growth by country ------------------------------------
    def _gdp_growth_by_country(self, records: List[Record]) -> List[Record]:
        continent = self._config.continent
        start_key = str(self._config.start_year)
        end_key = str(self._config.end_year)

        countries: List[Dict[str, Any]] = []
        for rec in records:
            if rec.get("Continent") != continent:
                continue
            start_val = rec.get(start_key)
            end_val = rec.get(end_key)
            if start_val is None or end_val is None:
                continue
            try:
                start_gdp = float(start_val)
                end_gdp = float(end_val)
            except (TypeError, ValueError):
                continue
            if start_gdp <= 0:
                continue
            growth_rate = (end_gdp - start_gdp) / start_gdp
            countries.append(
                {
                    "country": rec.get("Country Name"),
                    "start_year": self._config.start_year,
                    "end_year": self._config.end_year,
                    "start_gdp": start_gdp,
                    "end_gdp": end_gdp,
                    "growth_rate": growth_rate,
                }
            )

        return [
            {
                "metric": "gdp_growth_by_country",
                "continent": continent,
                "start_year": self._config.start_year,
                "end_year": self._config.end_year,
                "countries": sorted(
                    countries, key=lambda c: c["growth_rate"], reverse=True
                ),
            }
        ]

    # Metric 4: average GDP by continent ---------------------------------
    def _average_gdp_by_continent(self, records: List[Record]) -> List[Record]:
        start_year = self._config.start_year
        end_year = self._config.end_year

        agg: Dict[str, Dict[str, float]] = {}
        for rec in records:
            continent = rec.get("Continent")
            if not continent:
                continue
            bucket = agg.setdefault(continent, {"sum": 0.0, "count": 0.0})
            for year in range(start_year, end_year + 1):
                value = rec.get(str(year))
                if value is None:
                    continue
                try:
                    gdp = float(value)
                except (TypeError, ValueError):
                    continue
                bucket["sum"] += gdp
                bucket["count"] += 1.0

        averages = [
            {
                "continent": cont,
                "average_gdp": bucket["sum"] / bucket["count"]
                if bucket["count"]
                else 0.0,
            }
            for cont, bucket in agg.items()
        ]

        return [
            {
                "metric": "average_gdp_by_continent",
                "start_year": start_year,
                "end_year": end_year,
                "continents": sorted(
                    averages, key=lambda c: c["average_gdp"], reverse=True
                ),
            }
        ]

    # Metric 5: global GDP trend -----------------------------------------
    def _global_gdp_trend(self, records: List[Record]) -> List[Record]:
        start_year = self._config.start_year
        end_year = self._config.end_year

        trend: List[Dict[str, Any]] = []
        for year in range(start_year, end_year + 1):
            total = 0.0
            for rec in records:
                value = rec.get(str(year))
                if value is None:
                    continue
                try:
                    gdp = float(value)
                except (TypeError, ValueError):
                    continue
                total += gdp
            trend.append({"year": year, "global_gdp": total})

        return [
            {
                "metric": "global_gdp_trend",
                "start_year": start_year,
                "end_year": end_year,
                "trend": trend,
            }
        ]

    # Metric 6: fastest growing continent --------------------------------
    def _fastest_growing_continent(self, records: List[Record]) -> List[Record]:
        start_year = self._config.start_year
        end_year = self._config.end_year

        start_totals: Dict[str, float] = {}
        end_totals: Dict[str, float] = {}

        for rec in records:
            continent = rec.get("Continent")
            if not continent:
                continue
            start_val = rec.get(str(start_year))
            end_val = rec.get(str(end_year))
            if start_val is None or end_val is None:
                continue
            try:
                start_gdp = float(start_val)
                end_gdp = float(end_val)
            except (TypeError, ValueError):
                continue
            start_totals[continent] = start_totals.get(continent, 0.0) + start_gdp
            end_totals[continent] = end_totals.get(continent, 0.0) + end_gdp

        growth_rates: List[Dict[str, Any]] = []
        for continent, start_total in start_totals.items():
            end_total = end_totals.get(continent, 0.0)
            if start_total <= 0:
                continue
            growth_rate = (end_total - start_total) / start_total
            growth_rates.append(
                {
                    "continent": continent,
                    "start_year": start_year,
                    "end_year": end_year,
                    "start_gdp": start_total,
                    "end_gdp": end_total,
                    "growth_rate": growth_rate,
                }
            )

        fastest = (
            max(growth_rates, key=lambda c: c["growth_rate"]) if growth_rates else None
        )

        return [
            {
                "metric": "fastest_growing_continent",
                "start_year": start_year,
                "end_year": end_year,
                "result": fastest,
            }
        ]

    # Metric 7: consistent GDP decline -----------------------------------
    def _consistent_decline_countries(self, records: List[Record]) -> List[Record]:
        continent = self._config.continent
        end_year = self._config.end_year
        n_years = self._config.decline_years

        years = list(range(end_year - n_years + 1, end_year + 1))

        declining: List[Dict[str, Any]] = []
        for rec in records:
            if rec.get("Continent") != continent:
                continue
            values: List[float] = []
            valid = True
            for year in years:
                value = rec.get(str(year))
                if value is None:
                    valid = False
                    break
                try:
                    gdp = float(value)
                except (TypeError, ValueError):
                    valid = False
                    break
                values.append(gdp)
            if not valid or len(values) != len(years):
                continue
            if all(values[i] > values[i + 1] for i in range(len(values) - 1)):
                declining.append(
                    {
                        "country": rec.get("Country Name"),
                        "years": years,
                        "values": values,
                    }
                )

        return [
            {
                "metric": "consistent_gdp_decline",
                "continent": continent,
                "years": years,
                "countries": declining,
            }
        ]

    # Metric 8: continent contribution -----------------------------------
    def _continent_contribution(self, records: List[Record]) -> List[Record]:
        start_year = self._config.start_year
        end_year = self._config.end_year

        continent_totals: Dict[str, float] = {}

        for rec in records:
            continent = rec.get("Continent")
            if not continent:
                continue

            # Exclude global aggregates or other non-continent groupings
            if str(continent).lower() in {"global", "world"}:
                continue

            subtotal = 0.0
            for year in range(start_year, end_year + 1):
                value = rec.get(str(year))
                if value is None:
                    continue
                try:
                    gdp = float(value)
                except (TypeError, ValueError):
                    continue
                subtotal += gdp

            continent_totals[continent] = continent_totals.get(continent, 0.0) + subtotal

        # Compute total only from continent rows (no global aggregate)
        global_total = sum(continent_totals.values())

        contributions: List[Dict[str, Any]] = []
        for continent, total in continent_totals.items():
            share = (total / global_total) if global_total else 0.0
            contributions.append(
                {
                    "continent": continent,
                    "total_gdp": total,
                    "share_of_global_gdp": share,
                }
            )

        return [
            {
                "metric": "continent_contribution_to_global_gdp",
                "start_year": start_year,
                "end_year": end_year,
                "continents": sorted(
                    contributions,
                    key=lambda c: c["share_of_global_gdp"],
                    reverse=True,
                ),
            }
        ]

