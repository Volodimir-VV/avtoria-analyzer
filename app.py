import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

st.set_page_config(page_title="Аналізатор Avtoria.ua", page_icon="🚗", layout="wide")
st.title("🚗 Аналізатор авто з Avtoria.ua / auto.ria.com")
st.markdown("**Кидай посилання на оголошення — отримай повний розбір + рейтинг привабливості**")

url = st.text_input("Встав посилання на оголошення:", placeholder="https://auto.ria.com/auto_haval_dargo_39547958.html")

if st.button("🔍 Аналізувати авто"):
    if not url.startswith("https://auto.ria.com"):
        st.error("Встав правильне посилання з auto.ria.com")
        st.stop()
    
    with st.spinner("Парсимо сторінку..."):
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Витягуємо дані (робить по тексту — надійно)
            data = {}
            
            # Заголовок
            data["title"] = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Невідомо"
            
            # Ціна
            price_usd = re.search(r'(\d[\d\s]*)\$', response.text)
            data["price_usd"] = int(price_usd.group(1).replace(" ", "")) if price_usd else None
            
            # Рік
            year_match = re.search(r'(\d{4})\s*рік', response.text)
            data["year"] = int(year_match.group(1)) if year_match else None
            
            # Пробіг
            mileage_match = re.search(r'(\d[\d\s]*)\s*тис\.\s*км', response.text)
            data["mileage"] = int(mileage_match.group(1).replace(" ", "")) * 1000 if mileage_match else None
            
            # Місто
            location = soup.find(string=re.compile(r'([А-ЯІЇЄ][а-яієї]+),\s*[А-ЯІЇЄ]'))
            data["location"] = location.strip() if location else "Невідомо"
            
            # Двигун і коробка
            tech = soup.find_all(string=re.compile(r'(Бензин|Дизель|Електро|Гібрид|Автомат|Механіка|Робот)'))
            data["tech"] = " | ".join([t.strip() for t in tech[:4]]) if tech else "Невідомо"
            
            # VIN
            vin_match = re.search(r'([A-HJ-NPR-Z0-9]{17})', response.text)
            data["vin"] = vin_match.group(1) if vin_match else None
            
            # Власники + ДТП + страховка (текст з блоку історії)
            history_text = " ".join([p.get_text(strip=True) for p in soup.find_all("p") if "власник" in p.get_text().lower() or "ДТП" in p.get_text() or "страхов" in p.get_text().lower()])
            data["history"] = history_text[:500] + "..." if history_text else "Інформація не знайдена"
            
            # Проста перевірка на ДТП/власників
            owners = re.search(r'(\d)\s*власник', history_text.lower())
            data["owners"] = int(owners.group(1)) if owners else 1
            data["accidents"] = "Немає" if "немає" in history_text.lower() or "відсутні" in history_text.lower() else "Є згадки"
            
            # === Рейтинг привабливості ===
            score = 100
            current_year = datetime.now().year
            
            if data["year"]:
                age = current_year - data["year"]
                if data["mileage"]:
                    km_per_year = data["mileage"] / max(age, 1)
                    if km_per_year > 25000: score -= 35
                    elif km_per_year > 18000: score -= 20
                    elif km_per_year < 10000: score += 15
                if age > 10: score -= 15
                elif age < 3: score += 10
            
            if data["owners"] and data["owners"] > 2: score -= 25
            if data["accidents"] == "Є згадки": score -= 40
            
            if data["price_usd"] and data["year"] and data["mileage"]:
                # Бонус за нормальну ціну (дуже приблизно)
                expected_price = (data["year"] - 2000) * 1500 + 5000  # груба формула
                if data["price_usd"] < expected_price * 0.85: score += 20
            
            score = max(0, min(100, int(score)))
            data["rating"] = score
            
            # Вивід
            st.success("✅ Аналіз завершено!")
            
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("📋 Основні дані")
                st.write(f"**Модель:** {data['title']}")
                st.write(f"**Ціна:** {data['price_usd']} $")
                st.write(f"**Рік:** {data['year']}")
                st.write(f"**Пробіг:** {data['mileage']:,} км" if data["mileage"] else "**Пробіг:** не вказано")
                st.write(f"**Місто:** {data['location']}")
                st.write(f"**Техніка:** {data['tech']}")
                st.write(f"**VIN:** {data['vin'] or 'Не знайдено'}")
                st.write(f"**Власників:** {data['owners']}")
                st.write(f"**ДТП / страхові:** {data['accidents']}")
            
            with col2:
                st.subheader("⭐ Рейтинг привабливості")
                st.metric("Загальний рейтинг", f"{data['rating']}/100")
                if data["rating"] >= 80:
                    st.success("🔥 Дуже привабливий варіант!")
                elif data["rating"] >= 60:
                    st.info("👍 Нормальний варіант, можна дивитись")
                else:
                    st.warning("⚠️ Є питання — перевіряй уважно")
                
                st.caption("Рейтинг враховує: пробіг на рік, вік, кількість власників, ДТП, ціну відносно віку.")
            
            st.subheader("📜 Коротка історія з сайту")
            st.write(data["history"])
            
            if data["vin"]:
                st.info(f"🔗 Повна історія по VIN (платно від 150 грн): https://auto.ria.com/check-car/?vin={data['vin']}")
            
        except Exception as e:
            st.error(f"Помилка: {e}. Спробуй пізніше або перевір посилання.")

st.caption("Зроблено максимально просто. Якщо сайт трохи зміниться — код легко оновити. Хочеш версію Telegram-бота або Google Sheets — скажи!")
