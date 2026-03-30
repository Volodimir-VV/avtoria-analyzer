import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Порівняльник Avtoria", page_icon="🚗", layout="wide")
st.title("🚗 Порівняльник авто з AUTO.RIA — детальний аналіз")
st.markdown("**Встав посилання** (по одному на рядок) → таблиця з рейтингом, плюсами та мінусами")

urls_input = st.text_area(
    "Посилання на оголошення (по одному на рядок):",
    height=220,
    placeholder="https://auto.ria.com/uk/auto_volkswagen_t-roc_39656472.html\nhttps://..."
)

if st.button("🔍 Порівняти всі авто", type="primary"):
    urls = [url.strip() for url in urls_input.split("\n") if url.strip().startswith("https://auto.ria.com")]
    
    if not urls:
        st.error("Встав хоча б одне посилання")
        st.stop()
    
    with st.spinner(f"Аналізуємо {len(urls)} оголошень..."):
        cars = []
        current_year = datetime.now().year
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

        progress_bar = st.progress(0)

        for i, url in enumerate(urls):
            try:
                resp = requests.get(url, headers=headers, timeout=12)
                soup = BeautifulSoup(resp.text, "html.parser")
                text = resp.text.lower()

                car = {"link": url}

                # === Парсинг ===
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

                car["accidents"] = "Чиста" if any(x in text for x in ["дтп немає", "немає дтп", "без аварій"]) else "Є згадки / перевірити"

                # === ДЕТАЛЬНИЙ РЕЙТИНГ ===
                base = 50
                breakdown = {}

                # 1. Вік
                if car["year"]:
                    age = current_year - car["year"]
                    if age <= 2:   age_score = 25
                    elif age <= 4: age_score = 18
                    elif age <= 7: age_score = 10
                    else:          age_score = -15
                    breakdown["Вік"] = age_score
                else:
                    age_score = 0

                # 2. Пробіг на рік
                if car["year"] and car["mileage"]:
                    km_year = car["mileage"] / (current_year - car["year"])
                    if km_year < 12000: mileage_score = 18
                    elif km_year < 17000: mileage_score = 8
                    elif km_year < 25000: mileage_score = -10
                    else:                 mileage_score = -32
                    breakdown["Пробіг/рік"] = mileage_score
                else:
                    mileage_score = 0

                # 3. Ціна
                if car["price_usd"] and car["year"]:
                    expected = (current_year - car["year"]) * 1350 + 8500
                    if car["price_usd"] < expected * 0.82:
                        price_score = 22
                    elif car["price_usd"] < expected * 0.95:
                        price_score = 12
                    elif car["price_usd"] > expected * 1.25:
                        price_score = -28
                    else:
                        price_score = 0
                    breakdown["Ціна"] = price_score
                else:
                    price_score = 0

                # 4. Власники
                owners_score = 10 if car["owners"] == 1 else (0 if car["owners"] == 2 else -18)
                breakdown["Власники"] = owners_score

                # 5. Історія
                history_score = 25 if car["accidents"] == "Чиста" else -38
                breakdown["Історія"] = history_score

                # Фінальний рейтинг
                total_score = base + age_score + mileage_score + price_score + owners_score + history_score
                car["rating"] = max(10, min(100, int(total_score)))

                # === СИЛЬНІ та СЛАБКІ СТОРОНИ ===
                strengths = []
                weaknesses = []

                if age_score > 10: strengths.append("Свіжий рік")
                elif age_score < 0: weaknesses.append("Старіше авто")

                if mileage_score > 10: strengths.append("Низький пробіг на рік")
                elif mileage_score < -10: weaknesses.append("Великий пробіг")

                if price_score > 10: strengths.append("Добра ціна")
                elif price_score < -10: weaknesses.append("Ціна завищена")

                if owners_score > 0: strengths.append("1–2 власники")
                else: weaknesses.append(f"{car['owners']} власників")

                if history_score > 0: strengths.append("Чиста історія")
                else: weaknesses.append("Є згадки про ДТП / перевірка потрібна")

                car["strengths"] = " • ".join(strengths) if strengths else "—"
                car["weaknesses"] = " • ".join(weaknesses) if weaknesses else "—"

                cars.append(car)

            except:
                cars.append({"model": "Помилка", "link": url, "rating": 0, "strengths": "—", "weaknesses": "—"})

            progress_bar.progress((i + 1) / len(urls))

        # === ТАБЛИЦЯ ===
        df = pd.DataFrame(cars)
        df = df.sort_values(by="rating", ascending=False).reset_index(drop=True)

        display_df = df.copy()
        display_df["Ціна"] = display_df["price_usd"].apply(lambda x: f"{x:,} $" if pd.notna(x) else "—")
        display_df["Пробіг"] = display_df["mileage"].apply(lambda x: f"{x:,} км" if pd.notna(x) else "—")

        st.success(f"Проаналізовано {len([c for c in cars if c['rating'] > 10])} авто")

        st.dataframe(
            display_df[["model", "Ціна", "Рік", "Пробіг", "Місто", "Власників", "rating", "strengths", "weaknesses"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "model": "Модель",
                "rating": st.column_config.NumberColumn("Рейтинг", format="%d/100"),
                "strengths": "✅ Сильні сторони",
                "weaknesses": "⚠️ Слабкі сторони"
            }
        )

        # Пояснення алгоритму
        with st.expander("📊 Як саме рахується рейтинг (детально)"):
            st.markdown("""
            **База = 50 балів**  
            • Вік: до 2 років → +25, 3–4 → +18, 5–7 → +10  
            • Пробіг на рік: <12 тис → +18, >25 тис → -32  
            • Ціна: значно нижче ринку → +22, значно вище → -28  
            • Власники: 1 → +10, 3+ → -18  
            • Історія: чиста → +25, є згадки → -38  
            """)

        st.caption("Це максимально детальна версія. Якщо хочеш ще щось додати в рейтинг (наприклад, тип коробки, потужність, колір тощо) — скажи.")

st.caption("Працює на телефоні. Просто копіюй посилання зі свого пошуку і вставляй.")
