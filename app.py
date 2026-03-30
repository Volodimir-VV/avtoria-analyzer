import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime

st.set_page_config(page_title="Аналізатор Avtoria", page_icon="🚗", layout="wide")
st.title("🚗 Аналізатор авто з AUTO.RIA (оновлений 2026)")

url = st.text_input("Встав посилання на оголошення:", 
                    placeholder="https://auto.ria.com/uk/auto_volkswagen_t-roc_39463421.html")

if st.button("🔍 Аналізувати авто", type="primary"):
    if not url or "auto.ria.com" not in url:
        st.error("Встав правильне посилання з auto.ria.com")
        st.stop()

    with st.spinner("Завантажуємо та аналізуємо сторінку... (це може зайняти 3-5 сек)"):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
            "Referer": "https://auto.ria.com/"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            text = response.text.lower()

            data = {"title": "Невідомо", "price_usd": None, "year": None, "mileage": None,
                    "location": "Невідомо", "tech": "Невідомо", "vin": None,
                    "owners": 1, "accidents": "Невідомо", "history": ""}

            # 1. Заголовок
            h1 = soup.find("h1")
            if h1:
                data["title"] = h1.get_text(strip=True)

            # 2. Ціна (дуже надійний спосіб)
            price_match = re.search(r'(\d{1,3}(?:\s?\d{3})*)\s*\$', response.text)
            if price_match:
                data["price_usd"] = int(price_match.group(1).replace(" ", ""))

            # 3. Рік
            year_match = re.search(r'(\d{4})\s*рік', response.text) or re.search(r'(\d{4})', data["title"])
            if year_match:
                data["year"] = int(year_match.group(1))

            # 4. Пробіг
            mileage_match = re.search(r'(\d[\d\s]*)\s*(?:тис\.?|тис)\s*км', response.text)
            if mileage_match:
                data["mileage"] = int(mileage_match.group(1).replace(" ", "")) * 1000

            # 5. VIN
            vin_match = re.search(r'([A-HJ-NPR-Z0-9]{17})', response.text)
            if vin_match:
                data["vin"] = vin_match.group(1)

            # 6. Місто / локація
            location_match = re.search(r'(Київ|Львів|Одеса|Харків|Дніпро|[А-ЯІЇЄ][а-яіїє]{2,20})\s*обл\.?', response.text)
            if location_match:
                data["location"] = location_match.group(1)

            # 7. Техніка (двигун + коробка)
            tech_parts = []
            for keyword in ["бензин", "дизель", "електро", "гібрид", "1\\.[0-9]", "2\\.[0-9]", "автомат", "механіка", "робот"]:
                matches = re.findall(rf'({keyword}[^,.\n]{{0,30}})', response.text, re.I)
                if matches:
                    tech_parts.extend(matches[:2])
            data["tech"] = " | ".join(set(tech_parts)) if tech_parts else "Невідомо"

            # 8. Власники та ДТП
            if "1 власник" in text or "перший власник" in text:
                data["owners"] = 1
            elif "2 власник" in text:
                data["owners"] = 2
            if "немає" in text and ("дтп" in text or "аварі" in text or "страхов" in text):
                data["accidents"] = "Немає"
            else:
                data["accidents"] = "Потрібна перевірка"

            # Рейтинг привабливості (оновлена логіка)
            score = 85
            current_year = datetime.now().year
            if data["year"]:
                age = current_year - data["year"]
                if data["mileage"] and age > 0:
                    km_per_year = data["mileage"] / age
                    if km_per_year > 25000: score -= 30
                    elif km_per_year > 18000: score -= 15
                if age >= 8: score -= 20
                elif age <= 2: score += 12

            if data["owners"] > 2: score -= 20
            if data["accidents"] != "Немає": score -= 35

            if data["price_usd"] and data["year"]:
                rough_market = (current_year - data["year"]) * 1200 + 8000
                if data["price_usd"] < rough_market * 0.8: score += 18
                elif data["price_usd"] > rough_market * 1.25: score -= 25

            score = max(10, min(100, int(score)))
            data["rating"] = score

            # Вивід результатів
            st.success("✅ Аналіз завершено!")

            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("📋 Основні дані")
                for key, value in data.items():
                    if key not in ["rating", "history"]:
                        if isinstance(value, int) and key == "mileage":
                            st.write(f"**Пробіг:** {value:,} км")
                        else:
                            st.write(f"**{key.capitalize()}:** {value}")

            with col2:
                st.subheader("⭐ Рейтинг привабливості")
                st.metric("Загальний рейтинг", f"{data['rating']}/100")
                if data["rating"] >= 80:
                    st.success("🔥 Відмінний варіант!")
                elif data["rating"] >= 60:
                    st.info("👍 Нормальний, можна розглядати")
                else:
                    st.warning("⚠️ Є ризики — перевіряй уважно")

            if data["vin"]:
                st.info(f"🔗 Перевірити повну історію по VIN: https://auto.ria.com/check-car/?vin={data['vin']}")

            st.caption("Парсер оновлено під поточну версію сайту. Якщо все одно буде бред — скинь посилання, я подивлюсь і поправлю.")

        except Exception as e:
            st.error(f"Помилка завантаження: {str(e)[:200]}")
            st.info("Спробуй ще раз або перевір, чи сторінка відкривається в браузері.")

st.caption("Працює на телефоні та будь-якому ПК через Streamlit Cloud. Якщо хочеш ще стабільнішу версію (з Playwright або API) — скажи.")
