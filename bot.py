import asyncio
from tkinter.font import names

import requests
import urllib.parse
from urllib.parse import parse_qs

import sqlite3
import json
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext, Dispatcher
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import MediaGroup, InputFile
import aiogram

import logging
import random
import re

from async_timeout import timeout

API_TOKEN = '5806634842:AAG0o0n3PFbddP-Ji05XHbi7lNqMTOKo5BE'

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


async def parse(data):
    conn = sqlite3.connect('auto.db')
    cursor = conn.cursor()
    cursor.execute("select ip from proxy")
    http = cursor.fetchall()

    url = "https://api.av.by/offer-types/cars/filters/main/apply"

    headers = {
        "Accept": "*/*",
        "Accept-Language": "ru,en;q=0.9",
        "Content-Type": "application/json",
        "Origin": "https://cars.av.by",
        "Priority": "u=1, i",
        "Referer": "https://cars.av.by/",
        "Sec-CH-UA": '"Not/A)Brand";v="8", "Chromium";v="126", "YaBrowser";v="24.7", "Yowser";v="2.5"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 YaBrowser/24.7.0.0 Safari/537.36",
        "X-Device-Type": "web.desktop"
    }

    response = requests.post(url, headers=headers, json=data, proxies={'http': http[random.randint(0, len(http) - 1)]})

    return response


# Состояния
class Form(StatesGroup):
    waiting_for_link = State()
    parsing = State()


# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('auto.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS my_table (id INTEGER PRIMARY KEY)')
    conn.commit()
    conn.close()


init_db()

def calculate_image_size(width, height, color_depth=3):

    size_in_bytes = width * height * color_depth
    size_in_kb = size_in_bytes / 1024
    size_in_mb = size_in_kb / 1024
    return size_in_mb

def deep_set(dic, keys, value):
    key = keys[0]
    if len(keys) == 1:
        dic[key] = value
    else:
        if key not in dic:
            dic[key] = {}
        deep_set(dic[key], keys[1:], value)


async def format_data(query_string):
    parsed_query = parse_qs(query_string)
    result = {}

    for key, value in parsed_query.items():
        value = value[0]

        keys = re.split(r'\[|\]\[|\]', key)
        keys = [k for k in keys if k]  # Убираем пустые строки

        # Устанавливаем значение в итоговую структуру
        deep_set(result, keys, value)
    result.pop("page", None)
    result.pop("sort", None)
    result.pop("sorting", None)
    result.pop("page", None)
    result = {"properties": result}
    result["page"] = 1
    result["sort"] = 4
    result["sorting"] = 4
    return result

async def phone_mprice(article, cursor):

    url = f"https://api.av.by/offer-types/cars/price-statistics/offers/{article}"
    headers = {
        "accept": "*/*",
        "accept-language": "ru,en;q=0.9",
        "content-type": "application/json",
        "origin": "https://cars.av.by",
        "priority": "u=1, i",
        "referer": "https://cars.av.by/",
        "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "YaBrowser";v="24.7", "Yowser";v="2.5"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 YaBrowser/24.7.0.0 Safari/537.36",
        "x-device-type": "web.desktop"
    }
    cursor.execute("select ip from proxy")
    http = cursor.fetchall()
    response = requests.get(url, headers=headers, proxies={'http': http[random.randint(0, len(http) - 1)]}).json()

    title = response.get("title", [])
    name = ([f'{title["brand"]} {title["model"]} {title["generation"]} {title["year"]}'])
    medium_price = response.get("mediumPrice", [])["priceUsd"]
    return medium_price, name

async def get_photos(ad_photos):
    media = MediaGroup()
    size_img = 0
    for n, img in enumerate(ad_photos):
        if n == 8 or size_img > 8.5:
            break
        size_img += calculate_image_size(img["medium"]["width"], img["medium"]["height"])
        media.attach_photo(img["medium"]["url"])
    return media

async def get_ids(cursor, response):
    ids = [item["id"] for item in response.json().get("adverts", [])]

    cursor.execute(f'SELECT id FROM my_table WHERE id IN ({",".join("?" for _ in ids)})', ids)

    if cursor.fetchone() is None:
        ids = [(id,) for id in ids]

        # Используем параметризованный запрос для вставки
        cursor.executemany('INSERT INTO my_table (id) VALUES (?)', ids)


async def parse_ads(link, chat_id):
    conn = sqlite3.connect('auto.db')
    cursor = conn.cursor()
    coldown = 0
    while True:
        response = await parse(await format_data(link))
        if coldown == 0:
            await get_ids(cursor, response)
            conn.commit()
            coldown = 1
            continue
        for item in response.json().get("adverts", []):
            ad_id, ad_name, ad_photos, location = item["id"], item["properties"], item["photos"], item["shortLocationName"]
            try:
                description = item["description"]
            except:
                description = ""
            cursor.execute('SELECT id FROM my_table WHERE id = ?', (ad_id,))
            if cursor.fetchone() is None:
                cursor.execute(f'INSERT INTO my_table (id) VALUES ({str(ad_id)})')
                conn.commit()

                link = item["publicUrl"]
                article = link.split("/")[-1]
                spec= "\n".join([f"{prop['name']}: {prop['value']}"for prop in item["properties"]])
                medium_price, name = await phone_mprice(article, cursor)
                media_group = await get_photos(ad_photos)
                if len(media_group.media) > 1:
                    try:
                        await bot.send_media_group(chat_id=chat_id, media=media_group)
                    except aiogram.utils.exceptions.BadRequest as e:
                        print(name)
                        print(f"Ошибка: {e}")
                text = f"{name}\n{description}\n{spec}\n{location}\nСредняя цена: {medium_price}"
                if len(text) >= 4096:
                    text = text[:4030] + "..."
                text += f"\n{link}"
                await bot.send_message(chat_id, text)
                await asyncio.sleep(10)
        await asyncio.sleep(90)


@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await Form.waiting_for_link.set()
    await message.reply("Отправьте ссылку для начала парсинга.")


@dp.message_handler(state=Form.waiting_for_link)
async def process_link(message: types.Message, state: FSMContext):
    link = message.text
    await state.finish()  # Сброс состояния
    await message.reply("Парсинг начался.")

    asyncio.create_task(run_parsing(link, message.chat.id))


async def run_parsing(link, chat_id):
    while True:
        try:
            await parse_ads(link, chat_id)
        except:
            pass
        await asyncio.sleep(30)


@dp.message_handler(commands=['stop'])
async def cmd_stop(message: types.Message):
    await message.reply("Парсинг остановлен.")


@dp.message_handler(commands=['restart'])
async def cmd_restart(message: types.Message):
    await Form.waiting_for_link.set()
    await message.reply("Отправьте новую ссылку для парсинга.")


if __name__ == '__main__':
    from aiogram import executor

    executor.start_polling(dp, skip_updates=True)
