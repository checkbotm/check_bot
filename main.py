from aiogram import Bot, Dispatcher, types, executor
import socketio

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from configs import *
import requests
from locations import *

WEBSOCKET_URL = 'https://checkbot-webhook.onrender.com'

bot = Bot(token=API_TOKEN,)
dp = Dispatcher(bot)

sio = socketio.AsyncClient()

user_locations = {}


# Connect to WebSocket
async def connect_to_socketio():
    try:
        await sio.connect(WEBSOCKET_URL)
        print('Connected to WebSocket server')
    except Exception as e:
        print('Error connecting to WebSocket server:', e)


# Command /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    # Проверяем подключение к WebSocket серверу
    if not sio.connected:
        await connect_to_socketio()

    # Отправляем сообщение с ID пользователя
    await message.answer(f"Привет! Ваш ID: {message.from_user.id}")


@sio.on('message')
async def message(data):
    try:
        chat_id = int(data["chat_id"])
        text = data["message"]
        transaction_id = data.get("transaction_id")
        address = data.get("address")
        address = address.replace(' ', '+')
        account = data.get("account")


        keyboard = [
            [InlineKeyboardButton("Доставлено",
                                  callback_data=f'order_close:{transaction_id}:{account}')],
            [InlineKeyboardButton("Яндекс Карты", url=f"https://yandex.uz/maps/?text={address}")],
            [InlineKeyboardButton("Google Maps", url=f"https://www.google.com/maps/search/?api=1&query={address}")],
            [InlineKeyboardButton("2GIS", url=f"https://2gis.ru/?query={address}")],
            [InlineKeyboardButton("Добавить в маршрут", callback_data=f"route:{address}")]

        ]
        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await sio.emit('update', {'company_name': account})
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    except Exception as e:
        print("Error processing message:", e)

@sio.on('data_update')
async def message(account):
    await sio.emit('update', {'company_name': account})


# route
@dp.callback_query_handler(lambda call: 'route' in call.data)
async def route(callback_query: types.CallbackQuery):
    data_parts = callback_query.data.split(':')
    address = data_parts[1]

    chat_id = callback_query.message.chat.id

    data = user_locations.setdefault(chat_id, [])
    data.append(address)
    user_locations[chat_id] = data

    await bot.send_message(chat_id=chat_id, text=f"Местоположение {address} успешно добавлено ✅",
                           reply_markup=types.ReplyKeyboardMarkup(
                               keyboard=[
                                   [types.KeyboardButton(text="Проложить маршрут 🚘")],
                                   [types.KeyboardButton(text="Очистить маршрут 🗑")]],
                               resize_keyboard=True
                           ))


# Set a route
@dp.message_handler(lambda message: message.text == "Проложить маршрут 🚘")
async def set_a_route(message: types.Message):
    chat_id = message.chat.id
    if chat_id in user_locations:
        points = user_locations[chat_id]
        if len(points) > 1:
            url = get_yandex_map_link(points)

            # форматировать и сделать красиво
            formatted_points = [f"- {point} 📍" for point in points]
            message_text = '\n'.join(formatted_points)

            # создать кнопку
            keyboard = [[InlineKeyboardButton(text="Начинать маршрут 🚘", url=url)]]
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

            await bot.send_message(chat_id=chat_id, text=f"Маршрут готов ✅\n{message_text}", reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id=chat_id, text="Мало точек чтобы создать маршрут ❌")
    else:
        await bot.send_message(chat_id=chat_id, text="Маршрут пусто ❌")


# clear map
@dp.message_handler(lambda message: message.text == "Очистить маршрут 🗑")
async def clear_map(message: types.Message):
    chat_id = message.chat.id
    if chat_id in user_locations:
        del user_locations[chat_id]
        await bot.send_message(chat_id=chat_id, text="Корзина очищена ✅")
    else:
        await bot.send_message(chat_id=chat_id, text="Корзина пуста 🗑")


# get_location
@sio.on('get_location')
async def message(data):
    try:
        chat_id = data.get('chat_id')
        text = "Оператор запросил вашу геолокацию или трансляцию 📍\n "
        await bot.send_message(chat_id=chat_id, text=text, reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="Отправить местоположение📍", request_location=True)]],
            resize_keyboard=True
        ))
    except Exception as e:
        print("Error processing message:", e)


# close order
@dp.callback_query_handler(lambda call: 'order_close' in call.data)
async def order_close(callback_query: types.CallbackQuery):
    # Извлекаем spot_id и transaction_id из данных коллбэка
    data_parts = callback_query.data.split(':')
    transaction_id = data_parts[1]
    account = data_parts[2]

    # URL и данные транзакции
    url = f"{WEBSOCKET_URL}/order_close"

    data = {
        'transaction_id': transaction_id,
        'account': account
    }

    # Отправка запроса
    response = requests.post(url, json=data)

    # Отправляем сообщение о закрытии заказа

    if response.json()["response"]['err_code'] == 0:
        await bot.send_message(chat_id=callback_query.message.chat.id,
                               text=f"Чек № {transaction_id} успешно изменен статус на Доставлен")
    else:
        await bot.send_message(chat_id=callback_query.message.chat.id,
                               text=f"При закрытии чека № {transaction_id} произошла ошибка. Обратитесь к админстратору или попробойте позже")


# location
@dp.message_handler(content_types=types.ContentType.LOCATION)
async def handle_location(message: types.Message):
    latitude = message.location.latitude
    longitude = message.location.longitude
    chat_id = message.chat.id

    # Отправляем адрес, клавиатуру и вопрос в Telegram
    await bot.send_message(chat_id, f"Ваш адрес: {latitude} {longitude}")
    await sio.emit('location', {'latitude': latitude, 'longitude': longitude, 'courier_id': chat_id})


# live_location
@dp.edited_message_handler(content_types=types.ContentType.LOCATION)
async def handle_live_location(message: types.Message):
    latitude = message.location.latitude
    longitude = message.location.longitude
    chat_id = message.chat.id
    live_period = message.location.live_period
    await sio.emit('live_location', {'latitude': latitude, 'longitude': longitude, 'courier_id': chat_id,'live_period':live_period})


executor.start_polling(dp, skip_updates=True)
