import telebot
import json
from datetime import datetime
import os

# Загрузка конфигурации
try:
    with open('config.json', 'r', encoding='utf-8') as config_file:
        config = json.load(config_file)
except Exception as e:
    print(f"Ошибка загрузки конфигурации: {e}")
    exit()

TOKEN = config['TOKEN']
ADMINS = config['ADMINS']
bot = telebot.TeleBot(TOKEN, parse_mode='Markdown')  # Используем Markdown
user_data = {}
orders = []

# Логирование
def log_message(message):
    with open('logs.txt', 'a', encoding='utf-8') as log_file:
        log_file.write(f"{datetime.now()} - {message}\n")

# Генерация клавиатуры
def generate_markup(buttons, row_width=2):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=row_width)
    markup.add(*[telebot.types.KeyboardButton(button) for button in buttons])
    return markup

# Проверка администратора
def is_admin(chat_id):
    return chat_id in ADMINS

# Логирование ошибок
def log_error(error):
    with open('errors.log', 'a', encoding='utf-8') as error_file:
        error_file.write(f"{datetime.now()} - {error}\n")
# Обработка команды /start
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_data[chat_id] = {'state': 'city'}
    bot.send_message(chat_id, "🏙 Выберите ваш город:", reply_markup=generate_markup(config['CITIES'] + ['🏠 На главную']))

# Обработка кнопки "🏠 На главную"
@bot.message_handler(func=lambda message: message.text == '🏠 На главную')
def go_to_main(message):
    """
    Возвращает пользователя в главное меню.
    Учитывает права администратора при отображении кнопки `/admin`.
    """
    chat_id = message.chat.id

    # Кнопки главного меню
    buttons = ['/start']
    if is_admin(chat_id):
        buttons.append('/admin')  # Кнопка админ-меню только для администраторов

    bot.send_message(chat_id, "🏠 Вы в главном меню. Выберите действие:", reply_markup=generate_markup(buttons))


# Обработка выбора города
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'city')
def handle_city_selection(message):
    chat_id = message.chat.id
    text = message.text

    if text in config['CITIES']:
        user_data[chat_id]['city'] = text
        user_data[chat_id]['state'] = 'district'
        bot.send_message(chat_id, "📍 Выберите ваш район:", reply_markup=generate_markup(config['DISTRICTS'][text] + ['🏠 На главную']))
    else:
        bot.send_message(chat_id, "❌ Город не найден. Попробуйте снова.")

# Обработка выбора района
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'district')
def handle_district_selection(message):
    chat_id = message.chat.id
    text = message.text
    city = user_data[chat_id]['city']

    if text in config['DISTRICTS'].get(city, []):
        user_data[chat_id]['district'] = text
        user_data[chat_id]['state'] = 'product'
        bot.send_message(chat_id, "📦 Выберите продукт:", reply_markup=generate_markup([p['name'] for p in config['PRODUCTS'][city]] + ['🏠 На главную']))
    else:
        bot.send_message(chat_id, "❌ Район не найден. Попробуйте снова.")

# Обработка выбора продукта
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'product')
def handle_product_selection(message):
    chat_id = message.chat.id
    text = message.text
    city = user_data[chat_id]['city']

    product = next((p for p in config['PRODUCTS'][city] if p['name'] == text), None)
    if product:
        user_data[chat_id]['product'] = product
        user_data[chat_id]['state'] = 'payment'
        bot.send_message(chat_id, "💳 Выберите способ оплаты:", reply_markup=generate_markup([m['method'] for m in config['PAYMENT_METHODS']] + ['🏠 На главную']))
    else:
        bot.send_message(chat_id, "❌ Продукт не найден. Попробуйте снова.")

# Обработка способа оплаты
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'payment')
def handle_payment_method(message):
    chat_id = message.chat.id
    text = message.text

    payment_method = next((m for m in config['PAYMENT_METHODS'] if m['method'] == text), None)
    if payment_method:
        user_data[chat_id]['payment_method'] = text
        user_data[chat_id]['state'] = 'confirm'
        product = user_data[chat_id]['product']
        bot.send_message(chat_id, f"✅ Подтвердите ваш заказ:\n\n📦 Продукт: {product['name']}\n💵 Цена: {product['price']} ₽", reply_markup=generate_markup(['✅ Подтвердить', '❌ Отменить', '🏠 На главную']))
    else:
        bot.send_message(chat_id, "❌ Неверный способ оплаты. Попробуйте снова.")

# Обработка подтверждения заказа
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'confirm')
def handle_confirm_order(message):
    chat_id = message.chat.id
    text = message.text

    if text == '✅ Подтвердить':
        process_order(chat_id)
    elif text == '❌ Отменить':
        cancel_order(chat_id)
    else:
        bot.send_message(chat_id, "❓ Неизвестная команда. Используйте кнопки ниже.")
# Обработка подтверждения заказа
def process_order(chat_id):
    order_id = len(orders) + 1
    order = user_data.pop(chat_id)
    order['id'] = order_id
    order['chat_id'] = chat_id
    order['status'] = 'Ожидает подтверждения'
    orders.append(order)

    payment_details = generate_payment_details(order)
    bot.send_message(chat_id, f"✅ Ваш заказ №{order_id} подтверждён. Спасибо за покупку!\n\n{payment_details}")
    bot.send_message(chat_id, "🔔 Ваш заказ находится на подтверждении администратора.", reply_markup=generate_markup(['🏠 На главную']))

# Генерация реквизитов оплаты
def generate_payment_details(order):
    product_name = order['product']['name']
    product_price = order['product']['price']
    payment_method = order['payment_method']

    payment_details = config['PAYMENT_METHODS'][0]  # Placeholder for actual payment method details

    return (
        f"🔑 **Реквизиты для оплаты:**\n\n"
        f"🆔 **Номер заказа**: `{order['id']}`\n"
        f"📦 **Товар**: `{product_name}`\n"
        f"💵 **Сумма**: `{product_price} ₽`\n"
        f"💳 **Метод оплаты**: `{payment_method}`\n\n"
        f"💼 **Реквизиты**: `{payment_details['details']}`\n"
    )

# Отмена заказа пользователем
def cancel_order(chat_id):
    user_data.pop(chat_id, None)
    bot.send_message(chat_id, "❌ Ваш заказ отменён.", reply_markup=generate_markup(['🏠 На главную']))

# Уведомление пользователя
def notify_user(chat_id, message):
    try:
        bot.send_message(chat_id, message)
    except Exception as e:
        log_error(f"Ошибка уведомления пользователя {chat_id}: {e}")
# Админ-меню
@bot.message_handler(commands=['admin'])
def admin_menu(message):
    chat_id = message.chat.id
    if is_admin(chat_id):
        bot.send_message(
            chat_id,
            "🔧 Админ-меню:",
            reply_markup=generate_markup(['📋 Посмотреть заказы', '✅ Подтвердить платёж', '❌ Отменить заказ', '➕ Добавить товар', '➖ Удалить товар', '🏠 На главную'])
        )
    else:
        bot.send_message(chat_id, "❌ У вас нет прав доступа к админ-меню.")

# Обработка кнопок админ-меню
@bot.message_handler(func=lambda message: message.text in ['📋 Посмотреть заказы', '✅ Подтвердить платёж', '❌ Отменить заказ', '➕ Добавить товар', '➖ Удалить товар'] and is_admin(message.chat.id))
def handle_admin_buttons(message):
    chat_id = message.chat.id
    text = message.text

    if text == '📋 Посмотреть заказы':
        if orders:
            order_list = "\n".join(
                [f"🆔 {o['id']} - {o['status']} - {o['product']['name']} - {o['product']['price']} ₽" for o in orders])
            bot.send_message(chat_id, f"📑 Список заказов:\n\n{order_list}")
        else:
            bot.send_message(chat_id, "❌ Нет заказов.")
    elif text == '✅ Подтвердить платёж':
        bot.send_message(chat_id, "🔑 Введите ID заказа для подтверждения.")
        user_data[chat_id] = {'state': 'confirm_payment'}
    elif text == '❌ Отменить заказ':
        bot.send_message(chat_id, "🔑 Введите ID заказа для отмены.")
        user_data[chat_id] = {'state': 'cancel_order'}
    elif text == '➕ Добавить товар':
        bot.send_message(chat_id, "🔑 Введите название товара, цену и город через запятую.")
        user_data[chat_id] = {'state': 'add_product'}
    elif text == '➖ Удалить товар':
        bot.send_message(chat_id, "🔑 Введите название товара для удаления.")
        user_data[chat_id] = {'state': 'delete_product'}
    elif text == '🏠 На главную':
        bot.send_message(chat_id, "🏠 Вы вернулись в главное меню.")
# Добавление товара
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'add_product')
def add_product(message):
    chat_id = message.chat.id
    text = message.text
    try:
        product_name, price, city = text.split(',')
        price = int(price.strip())
        if city in config['PRODUCTS']:
            config['PRODUCTS'][city].append({'name': product_name.strip(), 'price': price})
            bot.send_message(chat_id, f"✅ Товар {product_name.strip()} добавлен.")
            log_message(f"Товар добавлен: {product_name.strip()} в {city}")
            user_data[chat_id] = {}
        else:
            bot.send_message(chat_id, "❌ Город не найден. Попробуйте снова.")
    except ValueError:
        bot.send_message(chat_id, "❌ Ошибка в формате. Попробуйте снова.")

# Удаление товара
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'delete_product')
def delete_product(message):
    chat_id = message.chat.id
    text = message.text
    for city, products in config['PRODUCTS'].items():
        product = next((p for p in products if p['name'] == text.strip()), None)
        if product:
            config['PRODUCTS'][city].remove(product)
            bot.send_message(chat_id, f"✅ Товар {text.strip()} удалён.")
            log_message(f"Товар удалён: {text.strip()}")
            user_data[chat_id] = {}
            return
    bot.send_message(chat_id, "❌ Товар не найден.")
# Обработка подтверждения платежа (админ)
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'confirm_payment' and is_admin(message.chat.id))
def confirm_payment(message):
    chat_id = message.chat.id
    text = message.text.strip()

    if text.isdigit():
        order_id = int(text)
        order = next((o for o in orders if o['id'] == order_id), None)
        if order:
            order['status'] = 'Оплачено'
            notify_user(order['chat_id'], f"✅ Ваш заказ №{order_id} подтверждён. Ожидайте доставки.")
            bot.send_message(chat_id, f"✅ Платёж для заказа №{order_id} подтверждён.")
            log_message(f"Платёж для заказа №{order_id} подтверждён.")
            user_data[chat_id] = {}  # Очистка состояния
        else:
            bot.send_message(chat_id, "❌ Заказ с таким ID не найден.")
    else:
        bot.send_message(chat_id, "❌ Пожалуйста, введите корректный ID заказа.")

# Обработка отклонения платежа (админ)
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'cancel_order' and is_admin(message.chat.id))
def cancel_order_by_admin(message):
    chat_id = message.chat.id
    text = message.text.strip()

    if text.isdigit():
        order_id = int(text)
        order = next((o for o in orders if o['id'] == order_id), None)
        if order:
            order['status'] = 'Отменён'
            notify_user(order['chat_id'], f"❌ Ваш заказ №{order_id} отменён администратором.")
            bot.send_message(chat_id, f"✅ Платёж для заказа №{order_id} отменён.")
            log_message(f"Платёж для заказа №{order_id} отменён.")
            user_data[chat_id] = {}  # Очистка состояния
        else:
            bot.send_message(chat_id, "❌ Заказ с таким ID не найден.")
    else:
        bot.send_message(chat_id, "❌ Пожалуйста, введите корректный ID заказа.")

# Обработка добавления нового товара (админ)
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'add_product' and is_admin(message.chat.id))
def add_product_by_admin(message):
    chat_id = message.chat.id
    text = message.text.strip()

    try:
        product_name, price, city = text.split(',')
        price = int(price.strip())

        if city in config['PRODUCTS']:
            config['PRODUCTS'][city].append({'name': product_name.strip(), 'price': price})
            bot.send_message(chat_id, f"✅ Товар {product_name.strip()} добавлен в {city}.")
            log_message(f"Товар добавлен: {product_name.strip()} в {city}")
            user_data[chat_id] = {}  # Очистка состояния
        else:
            bot.send_message(chat_id, "❌ Город не найден. Попробуйте снова.")
    except ValueError:
        bot.send_message(chat_id, "❌ Ошибка в формате. Пожалуйста, введите название товара, цену и город через запятую.")

# Обработка удаления товара (админ)
@bot.message_handler(func=lambda message: user_data.get(message.chat.id, {}).get('state') == 'delete_product' and is_admin(message.chat.id))
def delete_product_by_admin(message):
    chat_id = message.chat.id
    text = message.text.strip()

    for city, products in config['PRODUCTS'].items():
        product = next((p for p in products if p['name'] == text), None)
        if product:
            config['PRODUCTS'][city].remove(product)
            bot.send_message(chat_id, f"✅ Товар {text} удалён из {city}.")
            log_message(f"Товар {text} удалён из {city}")
            user_data[chat_id] = {}  # Очистка состояния
            return

    bot.send_message(chat_id, "❌ Товар не найден.")
# Сохранение конфигурации
def save_config():
    try:
        with open('config.json', 'w', encoding='utf-8') as config_file:
            json.dump(config, config_file, ensure_ascii=False, indent=4)
    except Exception as e:
        log_error(f"Ошибка сохранения конфигурации: {e}")

# Функция закрытия бота
def close_bot():
    save_config()
    log_message("Бот был остановлен.")

# Обработчик сигналов завершения работы
import signal
import sys

def signal_handler(sig, frame):
    close_bot()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

if __name__ == "__main__":
    try:
        log_message("Бот был запущен.")
        bot.polling(non_stop=True)
    except Exception as e:
        log_error(f"Ошибка работы бота: {e}")
        close_bot()





# Обработка команды /mybonus
@bot.message_handler(commands=['mybonus'])
def show_bonuses(message):
    chat_id = message.chat.id
    initialize_user_data(chat_id)  # Инициализируем данные пользователя
    bonuses = user_data[chat_id]['bonus']
    bot.send_message(chat_id, f"💰 Ваши бонусы: {bonuses} бонусов.")

# Обработка команды /myorders
@bot.message_handler(commands=['myorders'])
def show_orders(message):
    chat_id = message.chat.id
    initialize_user_data(chat_id)
    
    if user_data[chat_id]['orders']:
        order_list = "\n".join([f"🆔 {o['id']} - {o['status']} - {o['product']['name']} - {o['product']['price']} ₽" for o in user_data[chat_id]['orders']])
        bot.send_message(chat_id, f"📑 Ваши заказы:\n\n{order_list}")
    else:
        bot.send_message(chat_id, "❌ У вас нет заказов.")

# Обработка команды /referral
@bot.message_handler(commands=['referral'])
def referral(message):
    chat_id = message.chat.id
    initialize_user_data(chat_id)
    
    if user_data[chat_id]['referral_code'] is None:
        user_data[chat_id]['referral_code'] = str(chat_id)  # Используем chat_id как реферальный код
        bot.send_message(chat_id, f"🎁 Ваш реферальный код: {chat_id}")
    else:
        bot.send_message(chat_id, f"Ваш реферальный код: {user_data[chat_id]['referral_code']}")

# Обработка команды /payment_status
@bot.message_handler(commands=['payment_status'])
def payment_status(message):
    chat_id = message.chat.id
    order_id = message.text.split()[1]  # Пример: /payment_status <ID заказа>
    
    order = next((o for o in user_data[chat_id]['orders'] if o['id'] == int(order_id)), None)
    
    if order:
        payment_status = order['status']
        bot.send_message(chat_id, f"📊 Статус оплаты для заказа №{order_id}: {payment_status}")
    else:
        bot.send_message(chat_id, "❌ Заказ не найден.")
