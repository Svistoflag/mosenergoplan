
import requests

def geocode_address(address):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json"}
    headers = {"User-Agent": "DebtorRouteApp"}
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=5)
        if resp.status_code == 200 and resp.json():
            lat = float(resp.json()[0]["lat"])
            lon = float(resp.json()[0]["lon"])
            return lat, lon
    except Exception as e:
        print(f"Ошибка геокодирования: {e}")
    return None, None
