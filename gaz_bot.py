# gaz_bot.py - Главный файл нашего Telegram-бота для "Газ за час"

import xml.etree.ElementTree as ET  # Для чтения prices.xml
import pandas as pd                 # Для чтения warehouses.xlsx

# Aiogram для Telegram-бота
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram import F

# ========== 1. Загрузка данных ==========
def load_prices():
    """Загружает каталог товаров из prices.xml"""
    try:
        # Полный путь к файлу в песочнице
        tree = ET.parse('/home/workdir/attachments/prices.xml')
        root = tree.getroot()
        
        products = {}
        
        # Находим все предложения товаров (offer)
        for offer in root.findall(".//offer"):
            offer_id = offer.get('id')
            name_elem = offer.find('name')
            price_elem = offer.find('price')
            url_elem = offer.find('url')
            desc_elem = offer.find('description')
            
            name = name_elem.text if name_elem is not None else "Без названия"
            price = price_elem.text if price_elem is not None else "0"
            url = url_elem.text if url_elem is not None else ""
            description = desc_elem.text if desc_elem is not None else ""
            
            # Сохраняем по нижнему регистру для удобного поиска
            products[name.lower()] = {
                'id': offer_id,
                'name': name,
                'price': price,
                'url': url,
                'description': description[:200] + "..." if len(description) > 200 else description
            }
        
        print(f"✅ Успешно загружено {len(products)} товаров из prices.xml")
        return products
        
    except Exception as e:
        print(f"❌ Ошибка при чтении XML: {e}")
        return {}

def load_warehouses():
    """Загружает список складов из warehouses.xlsx"""
    try:
        df = pd.read_excel('/home/workdir/attachments/warehouses.xlsx', sheet_name="Филиалы")
        warehouses = []
        for _, row in df.iterrows():
            warehouses.append({
                'name': str(row.get('Название', '')),
                'status': str(row.get('Статус', '')),
                'address_short': str(row.get('Адрес (кратко)', '')),
                'work_time': str(row.get('Время работы', '')),
                'phone1': str(row.get('Телефон 1', '')),
                'address_full': str(row.get('Адрес (полный)', '')),
                'yandex_link': str(row.get('Ссылка на ЯК', ''))
            })
        print(f"✅ Успешно загружено {len(warehouses)} складов из Excel")
        return warehouses
    except Exception as e:
        print(f"❌ Ошибка при чтении Excel: {e}")
        return []

# ========== 2. Основная логика бота ==========
def find_product(query, products):
    """Ищет товар по запросу клиента (нечёткий поиск)"""
    if not query or not products:
        return None
    
    query_lower = query.lower().strip()
    
    # 1. Точное совпадение
    if query_lower in products:
        return products[query_lower]
    
    # 2. Поиск по частичному совпадению (лучшее совпадение)
    best_match = None
    best_score = 0
    
    for name, info in products.items():
        if query_lower in name:
            # Простая оценка: сколько слов из запроса есть в названии
            score = sum(1 for word in query_lower.split() if word in name)
            if score > best_score:
                best_score = score
                best_match = info
    
    if best_match:
        print(f"✅ Найден товар: {best_match['name']}")
        return best_match
    else:
        print(f"❌ Товар '{query}' не найден")
        return None

def get_nearest_warehouse(city="Москва", warehouses=None):
    """Ищет склад по городу"""
    if not warehouses:
        return "Нет данных о складах"
    
    city_lower = city.lower()
    for wh in warehouses:
        if (city_lower in wh['name'].lower() or 
            city_lower in wh['address_full'].lower() or 
            city_lower in wh['address_short'].lower()):
            return (f"{wh['name']}\n"
                    f"📍 {wh['address_short']}\n"
                    f"🕒 {wh['work_time']}\n"
                    f"📞 {wh['phone1']}\n"
                    f"🔗 {wh['yandex_link']}")
    
    # Если не нашли — возвращаем первый (Москва)
    if warehouses:
        wh = warehouses[0]
        return (f"{wh['name']}\n"
                f"📍 {wh['address_short']}\n"
                f"🕒 {wh['work_time']}\n"
                f"📞 {wh['phone1']}\n"
                f"🔗 {wh['yandex_link']}")
    return "Склад не найден"

# ========== Глобальные переменные для бота ==========
products = None
warehouses = None

# ========== 3. Формирование ответа клиенту ==========
def create_response(product_info, warehouse_info):
    """Создаёт красивый ответ для клиента"""
    if not product_info:
        return "К сожалению, не нашёл такой товар. Уточните, пожалуйста!"
    
    response = f"✅ {product_info['name']}\n"
    response += f"💰 Цена: {product_info['price']} руб.\n"
    response += f"🔗 Подробнее: {product_info['url']}\n\n"
    response += f"📍 Забрать можно здесь:\n{warehouse_info}"
    return response

# ========== Aiogram handlers ==========
async def start_cmd(message: types.Message):
    await message.answer(
        "👋 Здравствуйте! Я бот-консультант компании «Газ за час».\n\n"
        "Напишите, что вас интересует (например: «Пропан 50л», «Кислород 40л», «адреса складов»)"
    )

async def handle_message(message: types.Message):
    global products, warehouses
    if products is None:
        products = load_prices()
    if warehouses is None:
        warehouses = load_warehouses()
    
    text = message.text.strip()
    
    if "склад" in text.lower() or "адрес" in text.lower():
        wh_info = get_nearest_warehouse("Москва", warehouses)
        await message.answer(f"📍 Ближайший склад:\n{wh_info}")
        return
    
    # Поиск товара
    product = find_product(text, products)
    if product:
        wh_info = get_nearest_warehouse("Москва", warehouses)
        response = create_response(product, wh_info)
        await message.answer(response)
    else:
        await message.answer(
            "🙏 Уточните, пожалуйста, запрос.\n"
            "Например: «Пропан 21кг/50л» или «Кислород 40 литров»"
        )

# ========== 4. Запуск бота ==========
async def main():
    """Основная функция запуска Telegram-бота"""
    import os
    BOT_TOKEN = os.getenv("TELEGRAM_TOKEN")
    
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Ошибка: TELEGRAM_TOKEN не найден в переменных окружения!")
        print("Добавьте переменную TELEGRAM_TOKEN на Render.com")
        return
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Регистрируем обработчики
    dp.message.register(start_cmd, Command("start"))
    dp.message.register(handle_message)
    
    print("🤖 Telegram-бот 'Газ за час' запущен и ожидает сообщений в Telegram...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("🤖 Запуск Telegram-бота 'Газ за час'...")
    
    # Проверка: запускаемся ли мы на Render или в тестовой среде
    import os
    token = os.getenv("TELEGRAM_TOKEN")
    
    if token and token != "YOUR_BOT_TOKEN_HERE":
        # Запуск на сервере (Render)
        print("🌐 Запуск в режиме сервера (Render)")
        asyncio.run(main())
    else:
        # Тестовый режим в нашей песочнице
        print("\n🔧 Запускаем тестовый режим...")
        global products, warehouses
        products = load_prices()
        warehouses = load_warehouses()
        
        print("\n🧪 Давай протестируем бота! Напиши сообщение ниже (в следующем сообщении мне).")
        print("Примеры запросов:")
        print("- Пропан 21кг/50л")
        print("- Кислород 40л")
        print("- адреса складов")
        print("- Аргон")
        print("\n(Просто напиши мне в чат, и я обработаю через код бота)")
