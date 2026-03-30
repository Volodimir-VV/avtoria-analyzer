import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Порівняльник Avtoria", page_icon="🚗", layout="wide")
st.title("🚗 Порівняльник авто з AUTO.RIA (по посиланнях)")
st.markdown("**Встав кілька посилань** (по одному на рядок) — отримай таблицю порівняння + рейтинги")

urls_input = st.text_area(
    "Посилання на оголошення (по одному на рядок):",
    height=200,
    placeholder="https://auto.ria.com/uk/auto_volkswagen_t-roc_39656472.html\nhttps://auto.ria.com/uk/auto_volkswagen_t-roc_..."
)

if st.button("🔍 Порівняти всі авто", type="primary"):
    urls = [url.strip() for url in urls_input.split("\n") if url.strip().startswith("https://auto.ria.com")]
    
    if not urls:
        st.error("Встав хоча б одне правильне посилання")
        st.stop()
    
    if len(urls) > 15:
        st.warning("Занадто багато посилань. Аналізуємо максимум 15.")
        urls = urls[:15]
    
    with st.spinner(f"Аналізуємо {len(urls)} оголошень..."):
        cars = []
        current_year = datetime.now().year
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Accept-Language": "uk-UA,uk;q=0.9"
        }
        
        progress_bar = st.progress(0)
        
        for i, url in enumerate(urls):
            try:
                resp = requests.get(url, headers=headers, timeout=12)
                soup = BeautifulSoup(resp.text, "html.parser")
                text = resp.text
                
                car = {"link": url}
                
                # Модель
                h1 = soup.find("h1")
                car["model"] = h1.get_text(strip=True) if h1 else "Невідомо"
                
                # Ціна
                price_match = re.search(r"(\d[\d\s]{0,10})\s*\$", text)
                car["price_usd"] = int(price_match.group(1).replace(" ", "")) if price_match else None
                
                # Рік
                year_match = re.search(r"(\d{4})", car["model"])
                car["year"] = int(year_match.group(1)) if year_match else None
                
                # Пробіг
                mileage_match = re.search(r"(\d[\d\s]{0,8})\s*(тис\.?|тис)\s*км", text)
                car["mileage"] = int(mileage_match.group(1).replace(" ", "")) * 1000 if mileage_match else None
                
                # Місто
                city_match = re.search(r"(Київ|Львів|Одеса|Харків|Дніпро|Вінниця|[А-ЯІЇЄ][а-яіїє]{3,20})", text)
                car["location"] = city_match.group(1) if city_match else "Невідомо"
                
                # Власники та ДТП
                owners_match = re.search(r"(\d)\s*власник", text.lower())
                car["owners"] = int(owners_match.group(1)) if owners_match else 1
                car["accidents"] = "Немає" if "дтп немає" in text.lower() or "немає дтп" in text.lower() else "Перевірити"
                
                # Рейтинг
                score = 78
                if car["year"] and car["mileage"] and car["mileage"] > 0:
                    age = current_year - car["year"]
                    km_per_year = car["mileage"] / age
                    if km_per_year > 25000: score -= 30
                    elif km_per_year > 17000: score -= 15
                    elif km_per_year < 12000: score += 12
                
                if car["owners"] > 2: score -= 18
                if car["accidents"] != "Немає": score -= 35
                
                if car["price_usd"] and car["year"]:
                    expected = (current_year - car["year"]) * 1350 + 8500
                    if car["price_usd"] < expected * 0.85: score += 20
                    elif car["price_usd"] > expected * 1.28: score -= 25
                
                car["rating"] = max(10, min(100, int(score)))
                cars.append(car)
                
            except Exception:
                cars.append({"model": "Помилка завантаження", "link": url, "rating": 0})
            
            progress_bar.progress((i + 1) / len(urls))
        
        if not cars:
            st.error("Не вдалося отримати дані")
            st.stop()
        
        df = pd.DataFrame(cars)
        df = df.sort_values(by="rating", ascending=False).reset_index(drop=True)
        
        st.success(f"Порівняно {len([c for c in cars if c.get('rating', 0) > 0])} авто")
        
        # Форматована таблиця
        display_df = df.copy()
        display_df["Ціна"] = display_df["price_usd"].apply(lambda x: f"{x:,} $" if pd.notna(x) and x else "—")
        display_df["Пробіг"] = display_df["mileage"].apply(lambda x: f"{x:,} км" if pd.notna(x) and x else "—")
        display_df = display_df.rename(columns={
            "model": "Модель",
            "year": "Рік",
            "location": "Місто",
            "owners": "Власників",
            "rating": "Рейтинг"
        })
        
        st.dataframe(
            display_df[["Модель", "Ціна", "Рік", "Пробіг", "Місто", "Власників", "Рейтинг", "link"]],
            use_container_width=True,
            hide_index=True,
            column_config={"link": st.column_config.LinkColumn("Посилання", display_text="Відкрити")}
        )
        
        # Топ рекомендації
        st.subheader("🏆 Топ-3 найпривабливіших")
        for idx, row in df.head(3).iterrows():
            st.markdown(f"**{idx+1}. {row.get('model', '—')}** — Рейтинг **{row['rating']}**/100 — [Відкрити оголошення]({row['link']})")
        
        st.caption("Рейтинг враховує: вік, пробіг на рік, кількість власників, наявність ДТП, ціну відносно ринку. Це допоміжний інструмент — обов’язково роби діагностику та перевіряй VIN особисто.")

st.caption("Працює на телефоні та ПК. Просто копіюй посилання з пошуку та вставляй сюди. Якщо потрібно — можу додати фільтри (макс пробіг, бюджет тощо).")
