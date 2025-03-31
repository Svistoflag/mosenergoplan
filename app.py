
import streamlit as st
import pandas as pd
import re
from modules.geocode import geocode_address
from modules.dadata_api import CadastralProcessor

st.set_page_config(layout="wide")
st.title("Контроль и валидация адресов | МОСЭНЕРГОСБЫТ")

def is_probable_address(value):
    if not isinstance(value, str):
        return False
    if any(x in value.lower() for x in ["ул", "улица", "просп", "г.", "город", "д.", "дом", "р-н"]):
        return True
    return False

def is_kad_number(value):
    return isinstance(value, str) and bool(re.match(r"^\d{2}:\d{2}:\d{6,7}:\d+$", value))

uploaded_file = st.file_uploader("📁 Загрузите Excel-файл с данными", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.subheader("📋 Загруженные данные")
    st.dataframe(df)

    address_column = None
    for col in df.columns:
        sample = df[col].dropna().astype(str).head(50)
        score = sum([is_probable_address(v) or is_kad_number(v) for v in sample])
        if score / len(sample) > 0.3:
            address_column = col
            break

    if not address_column:
        st.error("❌ Не удалось автоматически определить столбец с адресами.")
    else:
        st.success(f"✅ Найден столбец с адресами: **{address_column}**")

        df["is_kadastr"] = df[address_column].apply(is_kad_number)
        df["is_address"] = df[address_column].apply(is_probable_address)
        df["status"] = df.apply(lambda row: "кадастр" if row["is_kadastr"] else (
            "адрес" if row["is_address"] else "некорректный"), axis=1)

        st.subheader("🟢 Валидные адреса")
        valid_df = df[df["status"] == "адрес"]
        st.dataframe(valid_df)

        st.subheader("🟡 Кадастровые номера")
        st.dataframe(df[df["status"] == "кадастр"])

        st.subheader("🔴 Некорректные строки")
        st.dataframe(df[df["status"] == "некорректный"])

        st.subheader("⚙️ Действия")
        col1, col2, col3 = st.columns(3)
        run_geocode = False
        convert_kadastr = False
        with col1:
            if st.button("📍 Геокодировать валидные адреса"):
                run_geocode = True
        with col2:
            st.button("🧠 Автоисправление некорректных строк")
        with col3:
            if st.button("📬 Конвертировать кадастровые номера"):
                convert_kadastr = True

        if convert_kadastr:
            st.info("⏳ Выполняется преобразование кадастровых номеров...")
            processor = CadastralProcessor()
            df = processor.process_dataframe(df, address_column)
            st.success(f"✅ Завершено: обработано {processor.stats['total']}, успешно — {processor.stats['success']}, ошибок — {processor.stats['errors']}")
            st.subheader("📋 Обновлённые адреса:")
            st.dataframe(df[[address_column]])

        if run_geocode:
            st.info("⏳ Выполняется геокодирование...")
            coords = []
            for index, row in valid_df.iterrows():
                addr = row[address_column]
                lat, lon = geocode_address(addr)
                coords.append((lat, lon))
            valid_df["lat"] = [c[0] for c in coords]
            valid_df["lon"] = [c[1] for c in coords]

            st.success("✅ Геокодирование завершено.")
            valid_coords = valid_df.dropna(subset=["lat", "lon"])
            st.subheader("🗺️ Карта валидных адресов")
            st.map(valid_coords[["lat", "lon"]])
