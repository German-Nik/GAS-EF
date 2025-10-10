import os
import sys
import streamlit as st
import pandas as pd

# --- чтобы Python видел папку src ---
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# Импорты модуля расчётов
import ghg_emission_calc.chem_data as chem_data_module
from ghg_emission_calc.chem_data import COMPONENT_DB as BASE_COMPONENT_DB
from ghg_emission_calc.calculator import (
    ef_from_molar,
    ef_from_mass,
)
from ghg_emission_calc.constants import CO2_DENSITIES

# ----------- Форматирование чисел -----------
def fmt(num, decimals=3):
    """Форматирование чисел с запятой в качестве разделителя"""
    if isinstance(num, (int, float)):
        return f"{num:.{decimals}f}".replace(".", ",")
    return str(num)

# ----------------- Стилизация (красные тона) -----------------
st.set_page_config(page_title="GHG EF — газ (Методика №371)", layout="wide")
st.markdown(
    """
    <style>
      .stApp {
        background-color: #fff5f5;
      }
      h1, h2, h3 {
        color: #b71c1c !important;
      }
      .stButton > button {
        background-color: #d32f2f;
        color: white;
        border-radius: 8px;
        border: none;
      }
      .stButton > button:hover {
        background-color: #b71c1c;
      }
      .stProgress > div > div {
        background: #b71c1c;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Калькулятор выбросов CO₂ для газообразного топлива ")
st.markdown("### С использованием коэффициента выбросов, определенного на основе компонентного состава топлива, Методика МПР №371")
st.markdown("## * Разработано ООО «КарбонЛаб»")

# ---------- Layout ----------
col1, col2 = st.columns([2, 1])

with col1:
    fuel_name = st.text_input("Название топлива", value="Природный газ")

    units = st.radio(
        "В каком виде задан состав?",
        ["Молярные доли (об.% / мол.%)", "Массовые доли (мас.%)"],
    )

    n = st.number_input("Сколько компонентов ввести?", min_value=1, max_value=16, value=3, step=1)

    st.markdown("**Ввод компонентов** (выберите из базы или 'Пользовательский'). Нулевые доли игнорируются.")
    rows = []

    # список для выбора: Название + формула
    all_options = [f"{v['name']} ({k})" for k, v in BASE_COMPONENT_DB.items()] + ["Пользовательский"]
    mapping = {f"{v['name']} ({k})": k for k, v in BASE_COMPONENT_DB.items()}

    used = set()  # чтобы не выбирать повторно

    for i in range(int(n)):
        # доступные варианты = все минус уже выбранные (но 'Пользовательский' всегда остаётся)
        available = [opt for opt in all_options if opt == "Пользовательский" or opt not in used]

        c0, c1, c2, c3, c4 = st.columns([2, 1, 1, 1, 1])
        comp_display = c0.selectbox(
            f"Компонент {i+1}",
            options=available,
            key=f"comp_select_{i}",
        )

        if comp_display != "Пользовательский":
            used.add(comp_display)

        val = c1.number_input(
            "Доля (%)",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            key=f"comp_val_{i}",
            format="%.4f",
        )

        if comp_display == "Пользовательский":
            cname = c2.text_input("Имя", value=f"X{i+1}", key=f"comp_name_{i}")
            cM = c3.number_input("M (г/моль)", min_value=0.0, value=44.01, key=f"comp_M_{i}")
            cnc = c4.number_input("nC", min_value=0, value=0, step=1, key=f"comp_nC_{i}")
            rows.append({
                "name": cname.strip() or f"X{i+1}",
                "val": float(val),
                "M": float(cM),
                "nC": int(cnc)
            })
        else:
            comp = mapping[comp_display]  # формула (ключ)
            comp_info = BASE_COMPONENT_DB[comp]
            c2.write(f"M = {fmt(comp_info['M'], 2)}")
            c3.write(f"nC = {comp_info['nC']}")
            c4.write("")
            rows.append({
                "name": comp,
                "val": float(val),
                "M": float(comp_info["M"]),
                "nC": int(comp_info["nC"])
            })

    # ---- Сумма введённых долей ----
    sum_val = sum(r["val"] for r in rows)
    col_sum1, col_sum2 = st.columns([1, 3])
    col_sum1.metric("Сумма долей", f"{fmt(sum_val)} %")

    if abs(sum_val - 100) < 1e-6:
        col_sum2.success("✅ Сумма = 100 %")
    else:
        col_sum2.info(f"ℹ️ Сумма отличается от 100 % на {fmt(sum_val - 100)} %")

    # --- выбор условий для плотности CO₂ ---
    temp_choice = st.selectbox(
        "Условия измерения (для плотности CO₂)",
        [
            "20 °C; 101,325 кПа → 1,8393 кг/м³",
            "0 °C; 101,325 кПа → 1,9768 кг/м³",
            "15 °C; 101,325 кПа → 1,8738 кг/м³",
        ],
        index=0,
    )

    if temp_choice.startswith("0 °C"):
        rho_co2 = CO2_DENSITIES["0C"]
    elif temp_choice.startswith("15 °C"):
        rho_co2 = CO2_DENSITIES["15C"]
    else:
        rho_co2 = CO2_DENSITIES["20C"]

    st.subheader("Расчет выбросов CO₂ при сжигании газообразного топлива")
    volume_value = st.number_input("Введите объём газа", min_value=0.0, value=1000.0, step=100.0)
    volume_unit = st.radio("Единицы объёма", ["м³", "тыс. м³"], horizontal=True)

    compute_btn = st.button("🔥 Вычислить выбросы CO₂", key="compute_btn")

with col2:
    st.markdown("### База компонентов (справочно)")
    df_comp = pd.DataFrame(
        [
            {
                "Формула": k,
                "Название": v["name"],
                "M (г/моль)": fmt(v["M"], 2),
                "nC": v["nC"],
            }
            for k, v in BASE_COMPONENT_DB.items()
        ]
    )
    st.dataframe(df_comp, use_container_width=True)

    st.markdown("### 📘 Формулы по методике МПР №371 (справочно)")

    st.latex(r"EF_{CO_{2},j,y} = \sum_{i=1}^{n} \left( W_{i,j,y} \times n_{C,i} \right) \times \rho_{CO_{2}} \times 10^{-2}")
    st.caption("Расчёт коэффициента выбросов CO₂ по молярному составу")

    st.latex(r"EF_{CO_{2},j,y} = \sum_{i=1}^{n} \left( \frac{W_{i,j,y} \times n_{C,i} \times 44{,}011}{M_{i}} \right) \times \rho_{j,y} \times 10^{-2}")
    st.caption("Расчёт коэффициента выбросов CO₂ по массовому составу")

    st.latex(r"E_{CO_{2},y} = \sum_{j=1}^{n} \left( FC_{j,y} \times EF_{CO_{2},j,y} \times OF_{j,y} \right)")
    st.caption("Расчёт массы выбросов CO₂ при сжигании объёма топлива")

# ----------------- Обработка клика -----------------
if "compute_btn" in locals() and compute_btn:
    # Собираем компоненты
    temp = {}
    for r in rows:
        if r["val"] <= 0:
            continue
        name = r["name"]
        temp[name] = {"val": r["val"], "M": r["M"], "nC": r["nC"]}

    if not temp:
        st.error("Нет введённых компонентов с ненулевой долей.")
        st.stop()

    # Добавляем пользовательские компоненты в базу
    for name, info in temp.items():
        if name not in chem_data_module.COMPONENT_DB:
            chem_data_module.COMPONENT_DB[name] = {"M": info["M"], "nC": info["nC"]}

    # Расчёт EF
    if units.startswith("Моляр"):
        mol_percent = {name: info["val"] for name, info in temp.items()}
        ef_val, _ = ef_from_molar(mol_percent, rho_co2)
    else:
        mass_percent = {name: info["val"] for name, info in temp.items()}
        ef_val, _ = ef_from_mass(mass_percent, rho_co2)

    st.success(f"Коэффициент EF_CO₂ = {fmt(ef_val, 5)} т CO₂ / тыс. м³")

    # Расчёт выбросов
    if volume_unit == "м³":
        volume_thousand = volume_value / 1000.0
    else:
        volume_thousand = volume_value

    emissions = ef_val * volume_thousand  # т CO2

    st.markdown(
        f"### 💨 Итоговые выбросы CO₂: **{fmt(emissions)} т** при сжигании **{fmt(volume_value)} {volume_unit}** топлива *«{fuel_name}»*"
    )