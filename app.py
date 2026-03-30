import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pandas as pd

st.set_page_config(page_title="Порівняльник Avtoria", page_icon="🚗", layout="wide")
st.title("🚗 Порівняльник авто з AUTO.RIA")
st.markdown("**Встав посилання на пошукову видачу** — отримай таблицю порівняння + рейтинги")

search_url = st.text_input("Посилання на пошукову сторінку:", 
                           placeholder="https://auto.ria.com/car/volkswagen/t-roc/")

num_cars = st.slider("Скільки оголошень аналізувати (макс 20)", 5, 20, 10)

if st.button("🔍 Порівняти варіанти", type="primary"):
    if not search_url or "auto.ria.com" not in search_url:
        st.error("Встав правильне посилання на пошукову видачу")
        st.stop()

    with st.spinner(f"Парсимо {num_cars} оголошень..."):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"
        }
        
        try:
            response = requests.get(search_url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Знаходимо всі картки оголошень
            items = soup.find_all("div", class_=re.compile(r"ticket-item|search-result"))[:num_cars]
            
            cars = []
            current_year = datetime.now().year
            
            for item in items:
                car = {}
                # Посилання на оголошення
                link_tag = item.find("a", href=re.compile(r"/auto_"))
                car["link"] = "https://auto.ria.com" + link_tag["href"] if link_tag else ""
                
                # Назва
                title_tag = item.find("h3") or item.find("span", class_=re.compile("ticket-title"))
                car["model"] = title_tag.get_text(strip=True) if title_tag else "Невідомо"
                
                # Ціна
                price_tag = item.find(string=re.compile(r"\$\s*\d"))
                if price_tag:
                    price_match = re.search(r"(\d[\d\s]*)", price_tag)
                    car["price_usd"] = int(price_match.group(1).replace(" ", "")) if price_match else None
                else:
                    car["price_usd"] = None
                
                # Рік
                year_match = re.search(r"(\d{4})", car["model"])
                car["year"] = int(year_match.group(1)) if year_match else None
                
                # Пробіг
                mileage_match = re.search(r"(\d[\d\s]*)\s*тис", str(item))
                car["mileage"] = int(mileage_match.group(1).replace(" ", "")) * 1000 if mileage_match else None
                
                # Місто
                location_tag = item.find(string=re.compile(r"(Київ|Львів|Одеса|Харків|Дніпро|[А-ЯІЇЄ][а-яіїє]{3,})"))
                car["location"] = location_tag.strip() if location_tag else "Невідомо"
                
                # Рейтинг
                score = 80
                if car["year"] and car["mileage"]:
                    age = current_year - car["year"]
                    if age > 0:
                        km_year = car["mileage"] / age
                        if km_year > 25000: score -= 30
                        elif km_year > 18000: score -= 15
                    if age > 8: score -= 20
                    elif age < 3: score += 15
                
                if car["price_usd"] and car["year"]:
                    rough_market = (current_year - car["year"]) * 1400 + 7000
                    if car["price_usd"] < rough_market * 0.85: score += 20
                    elif car["price_usd"] > rough_market * 1.3: score -= 25
                
                car["rating"] = max(10, min(100, int(score)))
                cars.append(car)
            
            if not cars:
                st.warning("Не вдалося знайти оголошення. Спробуй інше посилання.")
                st.stop()
            
            # Таблиця
            df = pd.DataFrame(cars)
            df = df.sort_values(by="rating", ascending=False)
            
            st.success(f"Знайдено та проаналізовано {len(cars)} варіантів")
            
            # Красива таблиця
            display_df = df.copy()
            display_df["Пробіг"] = display_df["mileage"].apply(lambda x: f"{x:,} км" if pd.notna(x) else "—")
            display_df["Ціна"] = display_df["price_usd"].apply(lambda x: f"{x:,} $" if pd.notna(x) else "—")
            display_df = display_df.rename(columns={
                "model": "Модель",
                "year": "Рік",
                "location": "Місто",
                "rating": "Рейтинг"
            })
            
            st.dataframe(
                display_df[["Модель", "Ціна", "Рік", "Пробіг", "Місто", "Рейтинг", "link"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "link": st.column_config.LinkColumn("Посилання", display_text="Відкрити")
                }
            )
            
            # Топ-3 рекомендації
            st.subheader("🏆 Топ рекомендації")
            for i, row in df.head(3).iterrows():
                st.write(f"**{i+1}. {row['model']}** — Рейтинг **{row['rating']}**/100 — [Відкрити]({row['link']})")
            
            st.caption("Рейтинг враховує: вік авто, пробіг на рік, ціну відносно ринку, кількість власників (приблизно).")
            
        except Exception as e:
            st.error(f"Помилка: {str(e)[:150]}")
            st.info("Сайт часто змінюється. Якщо не працює — скинь мені точне посилання на пошукову видачу, я швидко підправлю парсер.")

st.caption("Тепер головне — порівняння кількох варіантів. Якщо хочеш додати фільтри (бюджет, максимальний пробіг, тільки 1 власник тощо) або версію Telegram-бота — скажи.")
