from .chem_data import COMPONENT_DB
from .constants import M_CO2


def ef_from_molar(mol_percent, rho_co2, component_db=None):
    db = component_db or COMPONENT_DB
    total = 0.0
    breakdown = {}

    for name, value in mol_percent.items():
        if name not in db:
            raise KeyError(f"Компонент '{name}' отсутствует в базе данных.")
        nC = db[name]["nC"]
        contribution = value * nC * rho_co2 * 1e-2
        breakdown[name] = contribution
        total += contribution

    return total, breakdown


def ef_from_mass(mass_percent, rho_gas, component_db=None):
    db = component_db or COMPONENT_DB
    total = 0.0
    breakdown = {}

    for name, value in mass_percent.items():
        if name not in db:
            raise KeyError(f"Компонент '{name}' отсутствует в базе данных.")
        nC = db[name]["nC"]
        molar_mass = db[name]["M"]
        contribution = value * nC * M_CO2 / molar_mass * rho_gas * 1e-2
        breakdown[name] = contribution
        total += contribution

    return total, breakdown
