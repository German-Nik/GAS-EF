from typing import Dict, Tuple
import math

from ghg_emission_calc.chem_data import COMPONENT_DB
from ghg_emission_calc.constants import R, M_CO2, M_TO_KG, STANDARD_PRESSURE_PA

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
    # Формула МПР 371: EF = Σ(W_i × nC_i) × ρ_CO₂ × 10^(-2)
    # где W_i - молярные доли в процентах

    sum_nc = 0.0
    contributions = {}
    for comp, w_percent in molar_frac_percent.items():
        nC = COMPONENT_DB.get(comp, {}).get("nC", 0)
        # W_i × nC_i (уже в процентах!)
        contrib = w_percent * nC
        contributions[comp] = contrib
        sum_nc += contrib

    # Σ(W_i × nC_i) × ρ_CO₂ × 10^(-2)
    ef_t_per_1000m3 = sum_nc * rho_co2_kg_m3 * 0.01

    # Для breakdown тоже пересчитываем в итоговые выбросы
    contributions_t_per_1000m3 = {comp: contrib * rho_co2_kg_m3 * 0.01
                                 for comp, contrib in contributions.items()}

    return float(ef_t_per_1000m3), {c: float(contributions_t_per_1000m3[c]) for c in contributions_t_per_1000m3}

def ef_from_mass(mass_frac_percent: Dict[str, float],
                 rho_gas_kg_m3: float) -> Tuple[float, Dict[str, float]]:
    """
    EF (t CO2 / 1000 m3) from mass composition (percent).
    Returns (EF, breakdown_by_component)
    """
    # Формула МПР 371: EF = Σ(W_i × nC_i × 44.011 / M_i) × ρ_газа × 10^(-2)
    # где W_i - массовые доли в процентах

    s = 0.0
    contributions = {}
    for comp, w_percent in mass_frac_percent.items():
        if comp not in COMPONENT_DB:
            raise KeyError(f"Unknown component '{comp}' — требуется molar mass и nC.")
        nC = COMPONENT_DB[comp]["nC"]
        M = COMPONENT_DB[comp]["M"]  # g/mol
        # W_i × nC_i × 44.011 / M_i
        term = w_percent * nC * (M_CO2 / M)
        contributions[comp] = term
        s += term

    # Σ(W_i × nC_i × 44.011 / M_i) × ρ_газа × 10^(-2)
    ef_t_per_1000m3 = s * rho_gas_kg_m3 * 0.01

    # Для breakdown тоже пересчитываем в итоговые выбросы
    contributions_t_per_1000m3 = {comp: term * rho_gas_kg_m3 * 0.01
                                 for comp, term in contributions.items()}

    return float(ef_t_per_1000m3), {c: float(contributions_t_per_1000m3[c]) for c in contributions}
