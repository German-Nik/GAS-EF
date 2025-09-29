from typing import Dict, Tuple
import math

from ghg_emission_calc.chem_data import COMPONENT_DB
from ghg_emission_calc.constants import R, M_CO2, M_TO_KG, STANDARD_PRESSURE_PA

def normalize_percent_dict(d: Dict[str, float]) -> Dict[str, float]:
    s = sum(d.values())
    if s == 0:
        return d
    return {k: (v / s * 100.0) for k, v in d.items()}

def molar_frac_from_mass_frac(mass_frac_percent: Dict[str, float]) -> Dict[str, float]:
    """Convert mass % -> molar fraction (decimal) using molar masses from DB."""
    inv = {}
    for comp, w_percent in mass_frac_percent.items():
        if comp not in COMPONENT_DB:
            raise KeyError(f"Unknown component '{comp}' — нужно указать молярную массу и nC.")
        M = COMPONENT_DB[comp]["M"]  # g/mol
        inv[comp] = (w_percent / 100.0) / (M / 1000.0)  # proportional to mol/kg
    total = sum(inv.values())
    return {k: v / total for k, v in inv.items()}

def compute_mixture_molar_mass(molar_frac_decimal: Dict[str, float]) -> float:
    """M_mix in g/mol"""
    return sum(molar_frac_decimal[c] * COMPONENT_DB[c]["M"] for c in molar_frac_decimal)

def compute_gas_density_from_molar(molar_frac_decimal: Dict[str, float],
                                  T_k: float = 288.15,
                                  P_pa: float = STANDARD_PRESSURE_PA) -> float:
    """Ideal gas estimate of gas density (kg/m3)."""
    M_mix_gpermol = compute_mixture_molar_mass(molar_frac_decimal)
    M_mix_kgpermol = M_mix_gpermol * 1e-3
    rho = P_pa * M_mix_kgpermol / (R * T_k)
    return rho

def ef_from_molar(molar_frac_percent: Dict[str, float], rho_co2_kg_m3: float) -> Tuple[float, Dict[str, float]]:
    """
    EF (t CO2 / 1000 m3) from molar composition given in percent.
    Returns (EF, breakdown_by_component)
    """
    # normalize if sums not 100
    mol_percent = normalize_percent_dict(molar_frac_percent)
    w_dec = {c: mol_percent[c] / 100.0 for c in mol_percent}
    sum_nc = 0.0
    contributions = {}
    for c, w in w_dec.items():
        nC = COMPONENT_DB.get(c, {}).get("nC", 0)
        contrib = rho_co2_kg_m3 * w * nC  # kg/m3
        contributions[c] = contrib  # kg/m3
        sum_nc += w * nC
    ef_t_per_1000m3 = rho_co2_kg_m3 * sum_nc  # kg/m3 -> equals t/1000 m3 numerically
    # convert contributions to t/1000m3 as well
    contributions_t_per_1000m3 = {c: v for c, v in contributions.items()}
    # convert kg/m3 -> t/1000 m3 is numeric identity; but we present numbers as t/1000 m3
    return float(ef_t_per_1000m3), {c: float(contributions_t_per_1000m3[c]) for c in contributions_t_per_1000m3}

def ef_from_mass(mass_frac_percent: Dict[str, float],
                 rho_gas_kg_m3: float) -> Tuple[float, Dict[str, float]]:
    """
    EF (t CO2 / 1000 m3) from mass composition (percent).
    Returns (EF, breakdown_by_component)
    Formula: EF = rho_gas * sum( w_i_dec * nC_i * 44.011 / M_i )
    where M_i in g/mol, w_i_dec = percent/100
    """
    mass_percent = normalize_percent_dict(mass_frac_percent)
    w_dec = {c: mass_percent[c] / 100.0 for c in mass_percent}
    s = 0.0
    contributions = {}
    for c, w in w_dec.items():
        if c not in COMPONENT_DB:
            raise KeyError(f"Unknown component '{c}' — требуется molar mass и nC.")
        nC = COMPONENT_DB[c]["nC"]
        M = COMPONENT_DB[c]["M"]  # g/mol
        term = w * nC * (M_CO2 / M)
        contributions[c] = rho_gas_kg_m3 * term  # kg/m3 -> t/1000m3
        s += term
    ef_t_per_1000m3 = rho_gas_kg_m3 * s
    return float(ef_t_per_1000m3), {c: float(contributions[c]) for c in contributions}
