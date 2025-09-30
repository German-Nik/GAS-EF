# app.py
import os
import sys
import importlib

import streamlit as st
import pandas as pd

# --- чтобы Python видел папку src ---
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

# Импорты модуля расчётов
# ожидается, что у вас в src/ghg_emission_calc есть chem_data.py, calculator.py, constants.py
import ghg_emission_calc.chem_data as chem_data_module
from ghg_emission_calc.chem_data import COMPONENT_DB as BASE_COMPONENT_DB
from ghg_emission_calc.calculator import (
    ef_from_molar,
    ef_from_mass,
    molar_frac_from_mass_frac,
    compute_gas_density_from_molar,
)
from ghg_emission_calc.constants import CO2_DENSITIES

# ----------------- Стилизация (красные тона) -----------------
st.set_page_config(page_title="GHG EF — газ (Методика 371)", layout="wide")
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

st.title("Калькулятор выбросов CO₂ для газообразного топлива (Приказ №371)")
st.markdown("## * Приложение для учебных целей «Академии КарбонЛаб»")
# ---------- Layout ----------
col1, col2 = st.columns([2, 1])

with col1:
    fuel_name = st.text_input("Название топлива", value="Природный газ")

    units = st.radio(
        "В каком виде задан состав?",
        ["Молярные доли (об.% / мол.%)", "Массовые доли (мас.%)"],
    )

    n = st.number_input("Сколько компонентов ввести?", min_value=1, max_value=16, value=3, step=1)

    st.markdown("**Ввод компонентов** (выберите из базы или 'Custom'). Нулевые доли игнорируются.")
    rows = []
    for i in range(int(n)):
        # 5 колонок: выбор компонента, доля, (custom) имя, M, nC
        c0, c1, c2, c3, c4 = st.columns([2, 1, 1, 1, 1])
        comp = c0.selectbox(
            f"Компонент {i+1}",
            options=list(BASE_COMPONENT_DB.keys()) + ["Custom"],
            key=f"comp_select_{i}",
        )
        val = c1.number_input("Доля (%)", min_value=0.0, max_value=100.0, value=0.0, key=f"comp_val_{i}",format="%.4f")

        if comp == "Custom":
            cname = c2.text_input("Имя", value=f"X{i+1}", key=f"comp_name_{i}")
            cM = c3.number_input("M (г/моль)", min_value=0.0, value=44.01, key=f"comp_M_{i}")
            cnc = c4.number_input("nC", min_value=0, value=0, step=1, key=f"comp_nC_{i}")
            rows.append({"name": cname.strip() or f"X{i+1}", "val": float(val), "M": float(cM), "nC": int(cnc)})
        else:
            # показать справочные M и nC (не редактируемые)
            c2.write(f"M = {BASE_COMPONENT_DB[comp]['M']}")
            c3.write(f"nC = {BASE_COMPONENT_DB[comp]['nC']}")
            c4.write("")  # пустая ячейка
            rows.append(
                {
                    "name": comp,
                    "val": float(val),
                    "M": float(BASE_COMPONENT_DB[comp]["M"]),
                    "nC": int(BASE_COMPONENT_DB[comp]["nC"]),
                }
            )

    normalize = st.checkbox("Нормировать доли до 100% (если сумма ≠ 100%)", value=True)
    # ---- Сумма введённых долей ----
    sum_val = sum(r["val"] for r in rows)
    col_sum1, col_sum2 = st.columns([1, 3])
    col_sum1.metric("Сумма долей", f"{sum_val:.2f} %")

    if abs(sum_val - 100) < 1e-6:
        col_sum2.success("✅ Сумма = 100 %")
    else:
        col_sum2.warning(f"⚠️ Сумма отличается от 100 % на {sum_val-100:+.2f} %")

    # --- выбор условий для плотности CO2 ---
    temp_choice = st.selectbox(
        "Условия измерения (для плотности CO₂)",
        [
            "20 °C; 101,325 кПа → 1,8393 кг/м³",
            "0 °C; 101,325 кПа → 1,9768 кг/м³",
            "15 °C; 101,325 кПа → 1,8738 кг/м³",
        ],
    )

    if temp_choice.startswith("0 °C"):
        rho_co2 = CO2_DENSITIES["0C"]
        T_k = 273.15
    elif temp_choice.startswith("15 °C"):
        rho_co2 = CO2_DENSITIES["15C"]
        T_k = 288.15
    else:
        rho_co2 = CO2_DENSITIES["20C"]
        T_k = 293.15

    st.subheader("Расчет выбросов CO₂ при сжигании газообразного топлива")
    volume_value = st.number_input("Введите объём газа", min_value=0.0, value=1000.0, step=100.0)
    volume_unit = st.radio("Единицы объёма", ["м³", "тыс. м³"], horizontal=True)

    # Кнопка вычисления — обязательно создаём её здесь, чтобы переменная была доступна ниже
    compute_btn = st.button("🔥 Вычислить выбросы CO₂", key="compute_btn")


with col2:
    st.markdown("### База компонентов (справочно)")
    df_comp = pd.DataFrame(
        [
            {"Компонент": k, "M (г/моль)": v["M"], "nC": v["nC"]}
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
    # Собираем и суммируем одноимённые компоненты
    temp = {}
    for r in rows:
        name = r["name"]
        if r["val"] <= 0:
            continue
        if name in temp:
            temp[name]["val"] += r["val"]
        else:
            temp[name] = {"val": r["val"], "M": r["M"], "nC": r["nC"]}

    if not temp:
        st.error("Нет введённых компонентов с ненулевой долей.")
        st.stop()

    # Нормировка долей (если нужно)
    if normalize:
        s = sum(v["val"] for v in temp.values())
        if s == 0:
            st.error("Сумма долей равна нулю.")
            st.stop()
        for k in temp:
            temp[k]["val"] = temp[k]["val"] / s * 100.0

    # Обновляем модуль chem_data динамически для custom компонентов
    custom_to_add = {}
    for name, info in temp.items():
        if name not in chem_data_module.COMPONENT_DB:
            custom_to_add[name] = {"M": info["M"], "nC": info["nC"]}

    if custom_to_add:
        # добавляем кастомные компоненты в глобальную базу модуля
        chem_data_module.COMPONENT_DB.update(custom_to_add)

    # Формируем словарь долей для передачи в функции
    if units.startswith("Моляр"):
        # mol% expect names -> percentage numbers
        mol_percent = {name: info["val"] for name, info in temp.items()}
        ef_val, breakdown = ef_from_molar(mol_percent, rho_co2)
    else:
        mass_percent = {name: info["val"] for name, info in temp.items()}
        # если пользователь не предоставил плотность газа, оценим её через состав
        mol_frac_decimal = molar_frac_from_mass_frac(mass_percent)
        rho_gas = compute_gas_density_from_molar(mol_frac_decimal, T_k)
        ef_val, breakdown = ef_from_mass(mass_percent, rho_gas)

    # EF reported as т CO2 / тыс. м3
    st.success(f"Коэффициент EF_CO₂ = {ef_val:.6f} т CO₂ / тыс. м³")

    # Расчёт суммарных выбросов
    if volume_unit == "м³":
        volume_thousand = round(volume_value / 1000.0, 3)
    else:
        volume_thousand = round(volume_value, 3)

    emissions = ef_val * volume_thousand  # т CO2

    st.markdown(
    f"### 💨 Итоговые выбросы CO₂: **{emissions:.3f} т** при сжигании **{volume_value} {volume_unit}** топлива *«{fuel_name}»*"
)
