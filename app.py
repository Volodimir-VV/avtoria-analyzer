import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Порівняльник Avtoria", page_icon="🚗", layout="wide")
st.title("🚗 Порівняльник авто — чутливий рейтинг")
st.markdown("**Встав до 5 посилань** — тепер пробіг і ціна сильно впливають на рейтинг")

urls = []
for i in range(5):
    url = st.text_input(f"Посилання {i+1}:", key=f"url_{i}", 
                        placeholder="https://auto.ria.com/uk/auto_volkswagen_t-roc_...")
    if url.strip():
        urls.append(url.strip())

if st.button("🔍 Порівняти всі авто", type="primary"):
    valid_urls = [url for url in urls if url.startswith("https://auto.ria.com")]
    
    if not valid_urls:
        st.error("Встав хоча б одне посилання")
        st.stop()

    with st.spinner(f"Аналізуємо {len(valid_urls)} оголошень..."):
        cars = []
        current_year = datetime.now().year
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        for url in valid_urls:
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(resp.text, "html.parser")
                text = resp.text.lower()
                full_text = resp.text

                car = {"link": url}

                h1 = soup.find("h1")
                car["model"] = h1.get_text(strip=True) if h1 else "Невідомо"

                # Фото
                og_image = soup.find("meta", property="og:image")
                car["photo"] = og_image["content"] if og_image and og_image.get("content") else None

                # Ціна
                price_match = re.search(r"(\d[\d\s]{0,10})\s*\$", full_text)
                car["price_usd"] = int(price_match.group(1).replace(" ", "")) if price_match else None

                # Рік
                year_match = re.search(r"(\d{4})", car["model"])
                car["year"] = int(year_match.group(1)) if year_match else None

                # Пробіг
                mileage_match = re.search(r"(\d[\d\s]{0,8})\s*(тис\.?|тис)\s*км", full_text)
                car["mileage"] = int(mileage_match.group(1).replace(" ", "")) * 1000 if mileage_match else None

                # Власники
                owners_match = re.search(r"(\d)\s*власник", text)
                car["owners"] = int(owners_match.group(1)) if owners_match else 1

                # ДТП
                car["accidents"] = "Чиста" if any(x in text for x in ["дтп немає", "немає дтп", "без аварій", "немає офіційно"]) else "Перевірити"

                # === ЧУТЛИВИЙ РЕЙТИНГ ===
                base = 48
                age = current_year - car["year"] if car["year"] else 15

                # Вік
                age_score = max(-25, 30 - age * 4.2)

                # Пробіг на рік (дуже чутливий)
                if car["year"] and car["mileage"] and age > 0:
                    km_per_year = car["mileage"] / age
                    mileage_score = max(-45, 35 - (km_per_year - 8000) * 0.0028)
                else:
                    mileage_score = 0

                # Ціна (дуже чутлива)
                if car["price_usd"] and car["year"]:
                    expected = (current_year - car["year"]) * 1400 + 9000
                    deviation = ((car["price_usd"] - expected) / expected) * 100
                    price_score = max(-32, 32 - deviation * 1.1)
                else:
                    price_score = 0

                # Власники
                owners_score = max(-25, 18 - (car["owners"] - 1) * 14)

                # Історія
                history_score = 30 if car["accidents"] == "Чиста" else -42

                total = base + age_score + mileage_score + price_score + owners_score + history_score
                car["rating"] = max(10, min(100, round(total)))

                # Сильні / слабкі сторони
                strengths = []
                weaknesses = []
                if age_score > 8: strengths.append("Свіжий рік")
                if mileage_score > 15: strengths.append("Малий пробіг")
                if price_score > 15: strengths.append("Хороша ціна")
                if owners_score > 8: strengths.append("Мало власників")
                if history_score > 0: strengths.append("Чиста історія")

                if mileage_score < -15: weaknesses.append("Великий пробіг")
                if price_score < -12: weaknesses.append("Ціна висока")
                if owners_score < -8: weaknesses.append(f"{car['owners']} власників")
                if history_score < 0: weaknesses.append("Перевірити історію")

                car["strengths"] = " • ".join(strengths) if strengths else "—"
                car["weaknesses"] = " • ".join(weaknesses) if weaknesses else "—"

                cars.append(car)

            except:
                cars.append({"model": "Помилка завантаження", "photo": None, "rating": 0, 
                             "strengths": "—", "weaknesses": "—"})

        # Таблиця
        df = pd.DataFrame(cars)
        df = df.sort_values(by="rating", ascending=False).reset_index(drop=True)

        display_df = df.copy()
        display_df["Ціна"] = display_df["price_usd"].apply(lambda x: f"{x:,} $" if pd.notna(x) else "—")
        display_df["Пробіг"] = display_df["mileage"].apply(lambda x: f"{x:,} км" if pd.notna(x) else "—")
        display_df["Рік"] = display_df["year"]

        st.success(f"Проаналізовано {len(cars)} авто")

        st.dataframe(
            display_df[["photo", "model", "Ціна", "Рік", "Пробіг", "owners", "rating", "strengths", "weaknesses"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "photo": st.column_config.ImageColumn("Фото", width=80),
                "model": "Модель",
                "owners": "Власників",
                "rating": st.column_config.NumberColumn("Рейтинг", format="%d/100"),
                "strengths": "✅ Сильні сторони",
                "weaknesses": "⚠️ Слабкі сторони"
            }
        )

        with st.expander("📊 Як тепер рахується рейтинг"):
            st.markdown("База 48 + дуже чутливі коефіцієнти по пробігу та ціні. Повинна бути помітна різниця навіть між схожими авто.")

st.caption("Місто прибрано. Рейтинг став набагато чутливішим.")
