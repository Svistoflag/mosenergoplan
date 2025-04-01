import streamlit as st
import pandas as pd
import re
import requests
import json
import folium
from modules.geocode import geocode_address
from modules.dadata_api import CadastralProcessor
from streamlit_folium import st_folium

st.set_page_config(layout="wide")
st.title("МОСЭНЕРГОСБЫТ: Построение маршрута по адресам")

def is_probable_address(value):
    if not isinstance(value, str):
        return False
    value = value.lower()
    return any(word in value for word in ["ул", "улица", "просп", "г.", "город", "д.", "дом", "р-н", "посёлок", "переулок"])

def is_kad_number(value):
    return isinstance(value, str) and bool(re.search(r"\b\d{2,3}[:\s\-_]*\d+[:\s\-_]*\d+[:\s\-_]*\d+\b", value))

def get_route_osrm(coords):
    route_url = "http://router.project-osrm.org/route/v1/driving/"
    coord_str = ";".join([f"{lon},{lat}" for lat, lon in coords])
    response = requests.get(f"{route_url}{coord_str}?overview=full&geometries=geojson")
    if response.status_code == 200:
        return response.json()
    return None

uploaded_file = st.file_uploader("📁 Загрузите Excel-файл", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.subheader("📋 Загруженные данные")
    st.dataframe(df)

    address_column = None

    # Приоритетно проверяем четвёртую колонку
    if len(df.columns) >= 4:
        fourth_col = df.columns[3]
        sample = df[fourth_col].dropna().astype(str).head(50)
        if sum([is_probable_address(v) for v in sample]) / len(sample) > 0.3:
            address_column = fourth_col

    # Если не определена — используем автоанализ
    if not address_column:
        for col in df.columns:
            sample = df[col].dropna().astype(str).head(50)
            score = sum([is_probable_address(v) or is_kad_number(v) for v in sample])
            if score / len(sample) > 0.3:
                address_column = col
                break

    if not address_column:
        st.error("❌ Не удалось определить колонку с адресами.")
    else:
        st.success(f"✅ Определён столбец с адресами: **{address_column}**")

        df["contains_kadastr"] = df[address_column].apply(is_kad_number)
        kadastr_df = df[df["contains_kadastr"]]

        if st.button("🔁 Преобразовать кадастровые номера в адреса"):
            processor = CadastralProcessor()
            df[address_column] = df[address_column].astype(str).apply(processor.replace_cadastr_in_cell)
            st.success(f"✅ Преобразование завершено. Успешно: {processor.stats['success']}, Ошибки: {processor.stats['errors']}")

        df["is_address"] = df[address_column].apply(is_probable_address)
        valid_df = df[df["is_address"]]

        st.subheader("🟢 Все строки с валидными адресами")
        st.dataframe(valid_df[[address_column]])

        st.subheader("📍 Укажите стартовую точку маршрута")
        start_address = st.text_input("Введите адрес старта маршрута (например: Москва, Тверская 1)")
        build_route = st.button("🚗 Построить маршрут")

        if build_route and start_address:
            start_lat, start_lon = geocode_address(start_address)
            if not start_lat or not start_lon:
                st.error("❌ Не удалось геокодировать стартовый адрес.")
            else:
                coords = [(start_lat, start_lon)]
                address_list = []
                for addr in valid_df[address_column]:
                    lat, lon = geocode_address(addr)
                    if lat and lon:
                        coords.append((lat, lon))
                        address_list.append(addr)

                st.info("🧭 Выполняется маршрутизация...")
                route_data = get_route_osrm(coords)

                if route_data:
                    st.success("✅ Маршрут построен!")
                    route_coords = route_data["routes"][0]["geometry"]["coordinates"]
                    reversed_coords = [(lat, lon) for lon, lat in route_coords]

                    st.subheader("🗺️ Визуализация маршрута")
                    fmap = folium.Map(location=reversed_coords[0], zoom_start=12)
                    folium.Marker(reversed_coords[0], tooltip="Старт", icon=folium.Icon(color='green')).add_to(fmap)
                    for i, coord in enumerate(reversed_coords[1:], start=1):
                        folium.Marker(coord, tooltip=f"Точка {i}").add_to(fmap)
                    folium.PolyLine(reversed_coords, color="blue", weight=4.5, opacity=0.8).add_to(fmap)
                    st_folium(fmap, width=900, height=500)

                    st.subheader("📤 Экспорт маршрута")
                    geojson_route = {
                        "type": "FeatureCollection",
                        "features": [
                            {
                                "type": "Feature",
                                "geometry": {
                                    "type": "LineString",
                                    "coordinates": route_data["routes"][0]["geometry"]["coordinates"]
                                },
                                "properties": {
                                    "name": "Маршрут МОСЭНЕРГОСБЫТ"
                                }
                            }
                        ]
                    }
                    st.download_button("⬇️ Скачать маршрут (GeoJSON)", data=json.dumps(geojson_route), file_name="route.geojson", mime="application/geo+json")
                else:
                    st.error("⚠️ Ошибка при получении маршрута.")
