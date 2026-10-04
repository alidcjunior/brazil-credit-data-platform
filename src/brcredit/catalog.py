"""Catálogo das séries do BCB SGS usadas pela plataforma."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Series:
    code: int
    name: str
    unit: str
    periodicity: str  # "daily" | "monthly"
    default_start: date


# O IPCA começa 12 meses antes do período de análise (jun/2012) para viabilizar o acumulado 12m.
SERIES: dict[int, Series] = {
    432: Series(432, "Meta Selic (Copom)", "% a.a.", "daily", date(2012, 6, 1)),
    433: Series(433, "IPCA", "% no mês", "monthly", date(2011, 6, 1)),
}


def get_series(code: int) -> Series:
    try:
        return SERIES[code]
    except KeyError:
        valid = ", ".join(str(c) for c in sorted(SERIES))
        raise ValueError(f"Série {code} fora do catálogo. Séries válidas: {valid}") from None
