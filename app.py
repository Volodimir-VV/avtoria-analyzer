import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime

# === Мобільна оптимізація ===
st.set_page_config(
    page_title="Порівняльник Avtoria",
    page_icon="🚗",
    layout="wide",           # wide краще для ПК, але ми додамо mobile-friendly
    initial_sidebar_state="collapsed"  # ховаємо сайдбар на телефоні
)

# CSS для кращого вигляду на мобільних
st.markdown("""
<style>
    /* Загальний mobile-friendly стиль */
    @media (max-width: 768px) {
        .stDataFrame {font-size: 14px !important;}
        .stTextInput > div > div > input {font-size: 16px !important;}
        .stButton > button {width: 100% !important; height: 48px !important; font-size: 16px !important;}
    }
    
    /* Робимо таблицю більш читабельною */
    .dataframe th, .dataframe td {
        padding: 8px 4px !important;
        font-size: 14px;
    }
    
    /* Фото трохи менше на телефоні */
    img {
        max-height: 65px !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("🚗 Порівняльник авто")
st.markdown("**Зручна версія для телефону та ПК**")

# 5 полів для посилань
urls = []
for i in range(5):
    url = st.text_input(f"Посилання {i+1}:", key=f"url_{i}", 
                        placeholder="https://auto.ria.com/uk/auto_volkswagen_t-roc_...")
    if url.strip():
        urls.append(url.strip())

if st.button("🔍 Порівняти авто", type="primary", use_container_width=True):
    valid_urls = [url for url in urls if url.startswith("https://auto.ria.com")]
    
    if not valid_urls:
        st.error("Встав хоча б одне посилання з auto.ria.com")
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

                # Точна формула рейтингу (з попередньої версії)
                base = 45
                age = current_year - car["year"] if car["year"] else 15
                age_score = max(-25, 32 - age * 4.5)

                if car["year"] and car["mileage"] and age > 0:
                    km_per_year = car["mileage"] / age
                    sensitivity = 0.0038 if age <= 2 else 0.0029
                    mileage_score = max(-48, 38 - (km_per_year - 7000) * sensitivity)
                else:
                    mileage_score = 0

                if car["price_usd"] and car["year"]:
                    expected = (current_year - car["year"]) * 1350 + 10500
                    deviation = ((car["price_usd"] - expected) / expected) * 100
                    price_score = max(-35, 33 - deviation * 1.05)
                else:
                    price_score = 0

                owners_score = max(-25, 18 - (car["owners"] - 1) * 14)
                history_score = 30 if car["accidents"] == "Чиста" else -42

                total = base + age_score + mileage_score + price_score + owners_score + history_score
                car["rating"] = max(10, min(100, round(total)))

                # Сильні / слабкі
                strengths = []
                weaknesses = []
                if age_score > 10: strengths.append("Свіжий рік")
                if mileage_score > 15: strengths.append("Малий пробіг")
                if price_score > 12: strengths.append("Хороша ціна")
                if owners_score > 8: strengths.append("Мало власників")
                if history_score > 0: strengths.append("Чиста історія")

                if mileage_score < -15: weaknesses.append("Великий пробіг")
                if price_score < -15: weaknesses.append("Ціна завищена")
                if owners_score < -8: weaknesses.append(f"{car['owners']} власників")
                if history_score < 0: weaknesses.append("Перевірити історію")

                car["strengths"] = " • ".join(strengths) if strengths else "—"
                car["weaknesses"] = " • ".join(weaknesses) if weaknesses else "—"

                cars.append(car)

            except:
                cars.append({"model": "Помилка", "photo": None, "link": url, "rating": 0, "strengths": "—", "weaknesses": "—"})

        # Таблиця
        df = pd.DataFrame(cars)
        df = df.sort_values(by="rating", ascending=False).reset_index(drop=True)

        display_df = df.copy()
        display_df["Ціна"] = display_df["price_usd"].apply(lambda x: f"{x:,} $" if pd.notna(x) else "—")
        display_df["Пробіг"] = display_df["mileage"].apply(lambda x: f"{x:,} км" if pd.notna(x) else "—")
        display_df["Рік"] = display_df["year"]

        st.success(f"Проаналізовано {len(cars)} авто")

        st.dataframe(
            display_df[["photo", "model", "Ціна", "Рік", "Пробіг", "owners", "rating", "strengths", "weaknesses", "link"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "photo": st.column_config.ImageColumn("Фото", width=70),
                "model": "Модель",
                "owners": "Власників",
                "rating": st.column_config.NumberColumn("Рейтинг", format="%d/100"),
                "strengths": "✅ Сильні",
                "weaknesses": "⚠️ Слабкі",
                "link": st.column_config.LinkColumn("Відкрити", display_text="Перейти на auto.ria")
            }
        )

st.caption("Оптимізовано для телефону та комп’ютера. На Android/iOS просто відкрий посилання в Chrome.")
