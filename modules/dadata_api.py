
import re
import time
import requests
from typing import Union

DADATA_API_KEY = "26ccdbf16ac82b37ae82dfc43e62b7d72a198724"
DADATA_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/findById/address"

class DadataAPI:
    def __init__(self):
        self.api_url = DADATA_URL
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Token {DADATA_API_KEY}"
        }
        self.delay = 0.3
        self.last_request_time = 0

    def _throttle_request(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request_time = time.time()

    def get_address(self, cadastral_number: str) -> Union[str, None]:
        self._throttle_request()
        payload = {"query": cadastral_number}

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()

            if data.get("suggestions"):
                return data["suggestions"][0]["value"]
        except Exception as e:
            print(f"Ошибка запроса DaData: {str(e)}")
        return None

class CadastralProcessor:
    def __init__(self):
        self.dadata = DadataAPI()
        self.regex = re.compile(r"\b\d{2,3}[:\s\-_]*\d+[:\s\-_]*\d+[:\s\-_]*\d+\b")
        self.stats = {'total': 0, 'success': 0, 'errors': 0}

    def replace_cadastr_in_cell(self, cell_content: str) -> str:
        matches = self.regex.findall(str(cell_content))
        for match in matches:
            self.stats['total'] += 1
            cleaned = match.replace(" ", "").replace("-", "").replace("_", "")
            address = self.dadata.get_address(cleaned)
            if address:
                self.stats['success'] += 1
                cell_content = cell_content.replace(match, address)
            else:
                self.stats['errors'] += 1
        return cell_content

    def process_dataframe(self, df, column_name: str):
        df[column_name] = df[column_name].astype(str).apply(self.replace_cadastr_in_cell)
        return df
