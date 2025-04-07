import streamlit as st
import pandas as pd
import requests
import folium
import json
from streamlit_folium import st_folium
from io import BytesIO
from config import YANDEX_API_KEY, OSRM_SERVER_URL, STOP_TIME_MINUTES

st.set_page_config(layout="wide")
st.title("Полный маршрутизатор | Мосэнергосбыт")

uploaded_file = st.file_uploader("Загрузите Excel-файл", type=["xlsx"])
if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.dataframe(df.head())

    address_column = None
    for col in df.columns:
        if df[col].astype(str).str.contains(r"ул\.|г\.|д\.|переул|просп|шос|дом", case=False).sum() > 0:
            address_column = col
            break

    address_column = st.selectbox("Выберите колонку с адресами", df.columns, index=df.columns.get_loc(address_column) if address_column else 0)

    if st.button("Геокодировать"):
        coords = []
        for addr in df[address_column].astype(str):
            url = f"https://geocode-maps.yandex.ru/1.x/?format=json&apikey={YANDEX_API_KEY}&geocode={addr}"
            try:
                r = requests.get(url).json()
                pos = r["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]["pos"]
                lon, lat = map(float, pos.split())
                coords.append((lat, lon))
            except:
                coords.append((None, None))
        df["lat"], df["lon"] = zip(*coords)
        st.success("Геокодировано.")

    if "lat" in df.columns and "lon" in df.columns:
        valid_df = df.dropna(subset=["lat", "lon"])

        sort_by = st.selectbox("Сортировать маршрут по:", ["порядку в таблице", "по убыванию долга", "по возрастанию долга"])
        reverse_order = st.checkbox("Инвертировать маршрут")

        if "долг" in valid_df.columns and "по убыванию долга" in sort_by:
            valid_df = valid_df.sort_values(by="долг", ascending=False)
        elif "долг" in valid_df.columns and "по возрастанию долга" in sort_by:
            valid_df = valid_df.sort_values(by="долг", ascending=True)

        if reverse_order:
            valid_df = valid_df[::-1]

        if st.button("Построить маршрут (OSRM)"):
            points = ";".join([f"{lon},{lat}" for lat, lon in zip(valid_df["lat"], valid_df["lon"])])
            route_url = f"{OSRM_SERVER_URL}/route/v1/driving/{points}?overview=full&geometries=geojson"
            route_data = requests.get(route_url).json()
            coords = route_data["routes"][0]["geometry"]["coordinates"]
            duration = route_data["routes"][0]["duration"]

            m = folium.Map(location=[valid_df["lat"].mean(), valid_df["lon"].mean()], zoom_start=12)
            folium.PolyLine(locations=[[c[1], c[0]] for c in coords], color="blue").add_to(m)
            for i, row in valid_df.iterrows():
                folium.Marker([row["lat"], row["lon"]], tooltip=row[address_column]).add_to(m)

            st.subheader("Маршрут")
            st_folium(m, width=1000, height=600)

            total_minutes = duration / 60 + STOP_TIME_MINUTES * len(valid_df)
            st.info(f"⏱️ Примерное общее время маршрута: **{int(total_minutes)} минут**")

            # GeoJSON экспорт
            geojson = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {"description": "Оптимальный маршрут"}
                }]
            }
            geo_buffer = BytesIO()
            geo_buffer.write(json.dumps(geojson, ensure_ascii=False, indent=2).encode("utf-8"))
            geo_buffer.seek(0)
            st.download_button("📥 Скачать GeoJSON", geo_buffer, file_name="route.geojson", mime="application/geo+json")

            # GPX экспорт
            gpx = '<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="GPT">'
            gpx += "<trk><name>Маршрут</name><trkseg>"
            for c in coords:
                gpx += f'<trkpt lat="{c[1]}" lon="{c[0]}"></trkpt>'
            gpx += "</trkseg></trk></gpx>"
            gpx_buffer = BytesIO()
            gpx_buffer.write(gpx.encode("utf-8"))
            gpx_buffer.seek(0)
            st.download_button("📥 Скачать GPX", gpx_buffer, file_name="route.gpx", mime="application/gpx+xml")