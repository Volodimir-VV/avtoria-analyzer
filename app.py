import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Порівняльник T-Roc", page_icon="🚗", layout="wide")
st.title("🚗 Порівняльник Volkswagen T-Roc на AUTO.RIA")
st.markdown("**Аналіз пропозицій за твоїм пошуком** (2020+, бензин)")

search_url = st.text_input("Посилання на пошукову видачу:", 
                           value="https://auto.ria.com/uk/search/?search_type=2&category=1&all[0].any[0].brand=84&all[0].any[0].any[0].model=53084&all[0].any[0].year[0]=2020&all[1].any[0].fuel[0]=1&abroad=0&customs_cleared=1",
                           placeholder="Встав своє посилання")

num_results = st.slider("Кількість оголошень для аналізу", 5, 20, 12)

if st.button("🔍 Порівняти всі варіанти", type="primary"):
    if not search_url:
        st.error("Встав посилання")
        st.stop()

    with st.spinner(f"Завантажуємо та аналізуємо {num_results} оголошень..."):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Accept-Language": "uk-UA,uk;q=0.9"
        }
        
        try:
            resp = requests.get(search_url, headers=headers, timeout=20)
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Основні селектори (оновлені під поточний сайт)
            cards = soup.find_all(["div", "article"], class_=re.compile(r"ticket-item|search-result|car-card|listing-item"))[:num_results]
            
            if not cards:
                # Альтернативний пошук
                cards = soup.find_all("div", attrs={"data-id": True})[:num_results]
            
            cars = []
            current_year = datetime.now().year
            
            for card in cards:
                car = {}
                
                # Посилання
                link_tag = card.find("a", href=re.compile(r"/auto_.*\.html"))
                car["link"] = "https://auto.ria.com" + link_tag["href"] if link_tag and link_tag.get("href") else ""
                
                # Модель + рік
                title_tag = card.find(["h3", "h4", "span"], class_=re.compile(r"title|headline|ticket-title"))
                car["model"] = title_tag.get_text(strip=True) if title_tag else "Невідомо"
                
                # Ціна
                price_text = card.get_text()
                price_match = re.search(r"(\d[\d\s]{0,10})\s*\$", price_text)
                car["price_usd"] = int(price_match.group(1).replace(" ", "")) if price_match else None
                
                # Рік (з заголовка або тексту)
                year_match = re.search(r"(\d{4})", car["model"])
                car["year"] = int(year_match.group(1)) if year_match else None
                
                # Пробіг
                mileage_match = re.search(r"(\d[\d\s]{0,8})\s*(тис\.?|тис)\s*км", price_text)
                if mileage_match:
                    car["mileage"] = int(mileage_match.group(1).replace(" ", "")) * 1000
                else:
                    car["mileage"] = None
                
                # Місто
                city_match = re.search(r"(Київ|Львів|Одеса|Харків|Дніпро|Вінниця|Запоріжжя|[А-ЯІЇЄ][а-яіїє]{3,15})", price_text)
                car["location"] = city_match.group(1) if city_match else "Невідомо"
                
                # Розрахунок рейтингу
                score = 75
                if car["year"] and car["mileage"] and car["mileage"] > 0:
                    age = current_year - car["year"]
                    if age > 0:
                        km_per_year = car["mileage"] / age
                        if km_per_year > 25000:
                            score -= 32
                        elif km_per_year > 17000:
                            score -= 18
                        elif km_per_year < 12000:
                            score += 12
                
                if car["price_usd"] and car["year"]:
                    expected = (current_year - car["year"]) * 1300 + 9000  # груба ринкова оцінка
                    if car["price_usd"] < expected * 0.82:
                        score += 22
                    elif car["price_usd"] > expected * 1.25:
                        score -= 28
                
                car["rating"] = max(15, min(100, int(score)))
                cars.append(car)
            
            if not cars:
                st.error("Не вдалося знайти оголошення. Сайт, ймовірно, сильно захищений від парсингу (JS).")
                st.info("Спробуй відкрити сторінку в браузері та скинути мені 2-3 приклади повних посилань на окремі оголошення — зроблю аналіз по них.")
                st.stop()
            
            # Таблиця
            df = pd.DataFrame(cars)
            df = df.sort_values(by="rating", ascending=False).reset_index(drop=True)
            
            st.success(f"Проаналізовано {len(cars)} варіантів з твоєї видачі")
            
            # Форматування для відображення
            display_df = df.copy()
            display_df["Ціна"] = display_df["price_usd"].apply(lambda x: f"{x:,} $" if pd.notna(x) else "—")
            display_df["Пробіг"] = display_df["mileage"].apply(lambda x: f"{x:,} км" if pd.notna(x) else "—")
            display_df = display_df.rename(columns={
                "model": "Модель / Рік",
                "year": "Рік",
                "location": "Місто",
                "rating": "Рейтинг привабливості"
            })
            
            st.dataframe(
                display_df[["Модель / Рік", "Ціна", "Рік", "Пробіг", "Місто", "Рейтинг привабливості", "link"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "link": st.column_config.LinkColumn("Відкрити оголошення", display_text="Перейти")
                }
            )
            
            # Топ рекомендації
            st.subheader("🏆 Топ-3 найпривабливіших варіанти")
            for i, row in df.head(3).iterrows():
                st.markdown(f"**{i+1}. {row['model']}** — Рейтинг **{row['rating']}**/100 — Ціна {row['price_usd']:,}$ — [Відкрити]({row['link']})")
            
            st.caption("Рейтинг ≈ враховує пробіг на рік, вік, ціну відносно ринку. Це приблизний інструмент. Обов’язково перевіряй VIN, сервісну історію та авто особисто.")
            
        except Exception as e:
            st.error(f"Помилка завантаження: {str(e)[:200]}")
            st.info("Auto.ria активно захищається від автоматичного парсингу. Якщо таблиця пуста — найкраще рішення зараз: скинь мені 3–5 повних посилань на окремі оголошення, і я зроблю порівняння по них.")

st.caption("Поточна версія працює через Streamlit Cloud. Якщо парсинг видачі часто падає — можемо перейти на ручний ввод кількох посилань або Telegram-бота.")
