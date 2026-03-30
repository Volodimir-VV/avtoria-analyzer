import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Порівняльник Avtoria", page_icon="🚗", layout="wide")
st.title("🚗 Порівняльник авто — детальний аналіз")
st.markdown("**Встав до 5 посилань** на оголошення з AUTO.RIA")

# 5 окремих полів для посилань
urls = []
for i in range(5):
    url = st.text_input(f"Посилання {i+1}:", key=f"url_{i}", placeholder="https://auto.ria.com/uk/auto_volkswagen_t-roc_...")
    if url.strip():
        urls.append(url.strip())

if st.button("🔍 Порівняти всі авто", type="primary"):
    valid_urls = [url for url in urls if url.startswith("https://auto.ria.com")]
    
    if not valid_urls:
        st.error("Встав хоча б одне правильне посилання")
        st.stop()

    with st.spinner(f"Аналізуємо {len(valid_urls)} оголошень..."):
        cars = []
        current_year = datetime.now().year
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        for url in valid_urls:
            try:
                resp = requests.get(url, headers=headers, timeout=12)
                soup = BeautifulSoup(resp.text, "html.parser")
                text = resp.text.lower()

                car = {"link": url}

                # Основні дані
                h1 = soup.find("h1")
                car["model"] = h1.get_text(strip=True) if h1 else "Невідомо"

                price_match = re.search(r"(\d[\d\s]{0,10})\s*\$", resp.text)
                car["price_usd"] = int(price_match.group(1).replace(" ", "")) if price_match else None

                year_match = re.search(r"(\d{4})", car["model"])
                car["year"] = int(year_match.group(1)) if year_match else None

                mileage_match = re.search(r"(\d[\d\s]{0,8})\s*(тис\.?|тис)\s*км", resp.text)
                car["mileage"] = int(mileage_match.group(1).replace(" ", "")) * 1000 if mileage_match else None

                city_match = re.search(r"(Київ|Львів|Одеса|Харків|Дніпро|Вінниця|[А-ЯІЇЄ][а-яіїє]{3,20})", resp.text)
                car["location"] = city_match.group(1) if city_match else "Невідомо"

                owners_match = re.search(r"(\d)\s*власник", text)
                car["owners"] = int(owners_match.group(1)) if owners_match else 1

                car["accidents"] = "Чиста" if any(x in text for x in ["дтп немає", "немає дтп", "без аварій", "без дтп"]) else "Перевірити"

                # === Детальний рейтинг ===
                base = 50
                age_score = mileage_score = price_score = owners_score = history_score = 0

                if car["year"]:
                    age = current_year - car["year"]
                    age_score = 25 if age <= 2 else 18 if age <= 4 else 10 if age <= 7 else -15

                if car["year"] and car["mileage"] and car["mileage"] > 0:
                    km_year = car["mileage"] / (current_year - car["year"])
                    mileage_score = 18 if km_year < 12000 else 8 if km_year < 17000 else -10 if km_year < 25000 else -32

                if car["price_usd"] and car["year"]:
                    expected = (current_year - car["year"]) * 1350 + 8500
                    price_score = 22 if car["price_usd"] < expected * 0.82 else 12 if car["price_usd"] < expected * 0.95 else -28 if car["price_usd"] > expected * 1.25 else 0

                owners_score = 10 if car["owners"] == 1 else 0 if car["owners"] == 2 else -18
                history_score = 25 if car["accidents"] == "Чиста" else -38

                total = base + age_score + mileage_score + price_score + owners_score + history_score
                car["rating"] = max(10, min(100, int(total)))

                # Сильні та слабкі сторони
                strengths = []
                weaknesses = []

                if age_score >= 18: strengths.append("Свіжий рік")
                elif age_score <= -10: weaknesses.append("Старіше авто")

                if mileage_score >= 8: strengths.append("Низький пробіг на рік")
                elif mileage_score <= -10: weaknesses.append("Великий пробіг")

                if price_score >= 12: strengths.append("Хороша ціна")
                elif price_score <= -20: weaknesses.append("Ціна завищена")

                if owners_score > 0: strengths.append("Мало власників")
                else: weaknesses.append(f"{car['owners']} власників")

                if history_score > 0: strengths.append("Чиста історія")
                else: weaknesses.append("Історія потребує перевірки")

                car["strengths"] = " • ".join(strengths) if strengths else "—"
                car["weaknesses"] = " • ".join(weaknesses) if weaknesses else "—"

                cars.append(car)

            except Exception as e:
                cars.append({"model": "Помилка завантаження", "link": url, "rating": 0, 
                             "strengths": "—", "weaknesses": str(e)[:100]})

        # Таблиця
        if cars:
            df = pd.DataFrame(cars)
            df = df.sort_values(by="rating", ascending=False).reset_index(drop=True)

            display_df = df.copy()
            display_df["Ціна"] = display_df["price_usd"].apply(lambda x: f"{x:,} $" if pd.notna(x) and x else "—")
            display_df["Пробіг"] = display_df["mileage"].apply(lambda x: f"{x:,} км" if pd.notna(x) and x else "—")
            display_df["Рік"] = display_df["year"]

            st.success(f"Проаналізовано {len(cars)} авто")

            st.dataframe(
                display_df[["model", "Ціна", "Рік", "Пробіг", "location", "owners", "rating", "strengths", "weaknesses"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "model": "Модель",
                    "location": "Місто",
                    "owners": "Власників",
                    "rating": st.column_config.NumberColumn("Рейтинг", format="%d/100"),
                    "strengths": "✅ Сильні сторони",
                    "weaknesses": "⚠️ Слабкі сторони"
                }
            )

            with st.expander("📊 Як рахується рейтинг"):
                st.markdown("""
                **База = 50 балів**  
                - Вік: до 2 років → +25, 3-4 → +18, 5-7 → +10  
                - Пробіг на рік: <12 тис → +18, >25 тис → -32  
                - Ціна: значно нижче ринку → +22  
                - Власники: 1 → +10, 3+ → -18  
                - Історія: чиста → +25, проблеми → -38
                """)

    st.caption("Тепер зручно: 5 окремих полів + детальні плюси/мінуси.")
