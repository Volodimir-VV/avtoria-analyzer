import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Порівняльник Avtoria", page_icon="🚗", layout="wide")
st.title("🚗 Порівняльник авто — точний рейтинг")
st.markdown("**Встав до 5 посилань** — нова формула з кращою чутливістю до пробігу та ціни")

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

                og_image = soup.find("meta", property="og:image")
                car["photo"] = og_image["content"] if og_image and og_image.get("content") else None

                price_match = re.search(r"(\d[\d\s]{0,10})\s*\$", full_text)
                car["price_usd"] = int(price_match.group(1).replace(" ", "")) if price_match else None

                year_match = re.search(r"(\d{4})", car["model"])
                car["year"] = int(year_match.group(1)) if year_match else None

                mileage_match = re.search(r"(\d[\d\s]{0,8})\s*(тис\.?|тис)\s*км", full_text)
                car["mileage"] = int(mileage_match.group(1).replace(" ", "")) * 1000 if mileage_match else None

                owners_match = re.search(r"(\d)\s*власник", text)
                car["owners"] = int(owners_match.group(1)) if owners_match else 1

                car["accidents"] = "Чиста" if any(x in text for x in ["дтп немає", "немає дтп", "без аварій"]) else "Перевірити"

                # === НОВА ТОЧНА ФОРМУЛА ===
                base = 45
                age = current_year - car["year"] if car["year"] else 15

                # 1. Вік (сильніше для дуже нових авто)
                age_score = max(-25, 32 - age * 4.5)

                # 2. Пробіг на рік (дуже чутливий, особливо для нових авто)
                if car["year"] and car["mileage"] and age > 0:
                    km_per_year = car["mileage"] / age
                    # Для авто 2024-2025 пробіг карається сильніше
                    sensitivity = 0.0035 if age <= 2 else 0.0028
                    mileage_score = max(-48, 38 - (km_per_year - 7000) * sensitivity)
                else:
                    mileage_score = 0

                # 3. Ціна (реалістичніше порівняння)
                if car["price_usd"] and car["year"]:
                    # Очікувана ціна трохи скоригована для T-Roc
                    expected = (current_year - car["year"]) * 1350 + 10500
                    deviation = ((car["price_usd"] - expected) / expected) * 100
                    price_score = max(-35, 33 - deviation * 1.05)
                else:
                    price_score = 0

                # 4. Власники
                owners_score = max(-25, 18 - (car["owners"] - 1) * 14)

                # 5. Історія
                history_score = 30 if car["accidents"] == "Чиста" else -42

                total = base + age_score + mileage_score + price_score + owners_score + history_score
                car["rating"] = max(10, min(100, round(total)))

                # Сильні та слабкі сторони
                strengths = []
                weaknesses = []
                if age_score > 10: strengths.append("Свіжий рік")
                if mileage_score > 18: strengths.append("Дуже малий пробіг")
                elif mileage_score > 5: strengths.append("Малий пробіг")
                if price_score > 12: strengths.append("Хороша ціна")
                if owners_score > 8: strengths.append("Мало власників")
                if history_score > 0: strengths.append("Чиста історія")

                if mileage_score < -15: weaknesses.append("Великий пробіг")
                if price_score < -15: weaknesses.append("Ціна завищена")
                if owners_score < -8: weaknesses.append(f"{car['owners']} власників")
                if history_score < 0: weaknesses.append("Історія потребує перевірки")

                car["strengths"] = " • ".join(strengths) if strengths else "—"
                car["weaknesses"] = " • ".join(weaknesses) if weaknesses else "—"

                cars.append(car)

            except:
                cars.append({"model": "Помилка", "photo": None, "rating": 0, "strengths": "—", "weaknesses": "—"})

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

        with st.expander("📊 Нова формула рейтингу"):
            st.markdown("""
            - База = 45  
            - Пробіг став **дуже чутливим** (особливо для авто 2024-2025)  
            - Ціна тепер порівнюється реалістичніше  
            - Різниця між 3000 км і 10000 км повинна бути помітною
            """)

st.caption("Спробуй з тими самими 5 посиланнями. Якщо рейтинги все ще схожі — скинь скріншот таблиці, і я відразу підкоригую коефіцієнти.")
