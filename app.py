import streamlit as st
import requests
from bs4 import BeautifulSoup
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Порівняльник Avtoria", page_icon="🚗", layout="wide")
st.title("🚗 Порівняльник авто — детальний аналіз")
st.markdown("**Встав до 5 посилань** — отримай таблицю з фото, комплектацією та оновленим рейтингом")

# 5 окремих полів для посилань
urls = []
for i in range(5):
    url = st.text_input(f"Посилання {i+1}:", key=f"url_{i}", 
                        placeholder="https://auto.ria.com/uk/auto_volkswagen_t-roc_...")
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
                resp = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(resp.text, "html.parser")
                text = resp.text.lower()
                full_text = resp.text

                car = {"link": url}

                # Модель і рік
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

                # Місто (покращений пошук)
                city_patterns = [
                    r"(Київ|Львів|Одеса|Харків|Дніпро|Вінниця|Запоріжжя|Івано-Франківськ|[А-ЯІЇЄ][а-яіїє]{3,20})\s*(?:обл\.?|м\.)?",
                    r"Розташування[:\s]+([А-ЯІЇЄ][а-яіїє]{3,20})",
                    r"Місто[:\s]+([А-ЯІЇЄ][а-яіїє]{3,20})"
                ]
                car["location"] = "Не вказано"
                for pattern in city_patterns:
                    match = re.search(pattern, full_text)
                    if match:
                        city = match.group(1).strip()
                        if city.lower() not in ["продам", "продаж", "авто"]:
                            car["location"] = city
                            break

                # Власники
                owners_match = re.search(r"(\d)\s*власник", text)
                car["owners"] = int(owners_match.group(1)) if owners_match else 1

                # ДТП
                car["accidents"] = "Чиста" if any(x in text for x in ["дтп немає", "немає дтп", "без аварій", "немає офіційно зареєстрованих"]) else "Перевірити"

                # Коробка (тільки для відображення)
                if "dsg" in text or "робот" in text:
                    car["transmission"] = "DSG / Робот"
                elif "автомат" in text:
                    car["transmission"] = "Автомат"
                elif "механіка" in text:
                    car["transmission"] = "Механіка"
                else:
                    car["transmission"] = "Не вказано"

                # Комплектація (основні опції)
                options = []
                option_keywords = ["клімат", "камера", "підігрів", "круїз", "парктроник", "android auto", "carplay", "панорама", "led", "матрикс"]
                for kw in option_keywords:
                    if kw in text:
                        options.append(kw.capitalize())
                car["equipment"] = " • ".join(options[:6]) if options else "Не вказано"

                # === Рейтинг без урахування коробки ===
                base = 50
                scores = {}

                age = current_year - car["year"] if car["year"] else 10
                scores["Вік"] = 25 if age <= 2 else 18 if age <= 4 else 10 if age <= 7 else -18

                if car["year"] and car["mileage"]:
                    km_year = car["mileage"] / age
                    scores["Пробіг"] = 20 if km_year < 11000 else 12 if km_year < 16000 else -8 if km_year < 22000 else -35
                else:
                    scores["Пробіг"] = 0

                if car["price_usd"] and car["year"]:
                    expected = (current_year - car["year"]) * 1400 + 9000
                    deviation = (car["price_usd"] - expected) / expected * 100
                    scores["Ціна"] = 24 if deviation < -18 else 15 if deviation < -8 else -22 if deviation > 25 else 0
                else:
                    scores["Ціна"] = 0

                scores["Власники"] = 12 if car["owners"] == 1 else 3 if car["owners"] == 2 else -20
                scores["Історія"] = 25 if car["accidents"] == "Чиста" else -40

                total = base + sum(scores.values())
                car["rating"] = max(10, min(100, int(total)))

                # Сильні та слабкі сторони
                strengths = [k for k, v in scores.items() if v >= 12]
                weaknesses = [k for k, v in scores.items() if v <= -15]

                car["strengths"] = " • ".join(strengths) if strengths else "—"
                car["weaknesses"] = " • ".join(weaknesses) if weaknesses else "—"

                cars.append(car)

            except Exception:
                cars.append({"model": "Помилка завантаження", "photo": None, "location": "—", 
                             "equipment": "—", "rating": 0, "strengths": "—", "weaknesses": "—"})

        # Таблиця
        if cars:
            df = pd.DataFrame(cars)
            df = df.sort_values(by="rating", ascending=False).reset_index(drop=True)

            display_df = df.copy()
            display_df["Ціна"] = display_df["price_usd"].apply(lambda x: f"{x:,} $" if pd.notna(x) else "—")
            display_df["Пробіг"] = display_df["mileage"].apply(lambda x: f"{x:,} км" if pd.notna(x) else "—")
            display_df["Рік"] = display_df["year"]

            st.success(f"Проаналізовано {len(cars)} авто")

            st.dataframe(
                display_df[["photo", "model", "Ціна", "Рік", "Пробіг", "location", "owners", "transmission", "equipment", "rating", "strengths", "weaknesses"]],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "photo": st.column_config.ImageColumn("Фото", width=80),
                    "model": "Модель",
                    "location": "Місто",
                    "owners": "Власників",
                    "transmission": "Коробка",
                    "equipment": "Комплектація",
                    "rating": st.column_config.NumberColumn("Рейтинг", format="%d/100"),
                    "strengths": "✅ Сильні сторони",
                    "weaknesses": "⚠️ Слабкі сторони"
                }
            )

            with st.expander("📊 Як рахується рейтинг (без коробки)"):
                st.markdown("""
                **База = 50 балів**  
                - Вік, Пробіг на рік, Ціна відносно ринку, Власники, Історія (ДТП)  
                Коробка **не впливає** на рейтинг, лише показується для інформації.
                """)

st.caption("Місто витягується точніше. Комплектація показує наявні опції або «Не вказано».")
