import telebot
from telebot import types
import sqlite3
import os
from dotenv import load_dotenv

# загрузка переменных окружения из файла .env
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')

# создание объекта бота
bot = telebot.TeleBot(BOT_TOKEN)

# словарь для хранения запросов на чат
chat_requests = {}
# словарь для хранения активных чатов
chats = {}
# словарь для хранения активных чатов
active_chats = {}
# словарь для хранения соединений между чатами
connections = {}

# класс для представления сообщений в чате
class ChatMessage:
    def __init__(self, sender, text):
        self.sender = sender
        self.text = text

# обработчик команды /stop
@bot.message_handler(commands=['stop'])
def stop_chat(message):
    if message.chat.id in active_chats:
        # удаление активного чата и связанных данных
        chat_id = message.chat.id
        partner_chat_id = connections.get(chat_id)
        del active_chats[chat_id]
        if partner_chat_id:
            del active_chats[partner_chat_id]
        connections[chat_id] = None
        if partner_chat_id:
            connections[partner_chat_id] = None
        # отправка сообщения об остановке чата
        bot.send_message(chat_id, 'Переписка остановлена. Для начала новой переписки введи команду /match')
        if partner_chat_id:
            bot.send_message(partner_chat_id, 'Переписка остановлена. Для начала новой переписки введи команду /match')
        # добавление кнопки для поиска
        search_button = types.KeyboardButton('Поиск🔍')
        search_keyboard = types.ReplyKeyboardMarkup(row_width=1)
        search_keyboard.add(search_button)

# обработчик обмена сообщениями между пользователями
@bot.message_handler(func=lambda message: message.chat.id in active_chats)
def handle_messages(message):
    chat_id = message.chat.id
    current_chat = active_chats[chat_id]
    if (message.text != '/stop') and (message.text != '/help'):
        # определение отправителя сообщения
        if message.from_user.username:
            sender = "@" + message.from_user.username
        else:
            sender = message.from_user.first_name

        # добавление сообщения в активный чат
        current_chat.append(ChatMessage(sender, message.text))

        # отправка сообщения собеседнику
        if chat_id in connections:
            receiver_chat_id = connections[chat_id]
            receiver_message = f"{sender}: {message.text}"
            bot.send_message(receiver_chat_id, receiver_message)
        else:
            bot.send_message(chat_id, 'Ожидание собеседника...')

    if message.text == '/help':
        # вызов справки
        show_help(message)

    if message.text == '/stop':
        # остановка чата
        stop_chat(message)

# обработчик для начала чата с выбранным пользователем
@bot.message_handler(func=lambda message: message.text.startswith('Начать чат с'))
def start_chat(message):
    chat_initiator_id = message.chat.id
    if chat_initiator_id in active_chats:
        bot.send_message(chat_initiator_id, 'В данный момент вы уже ведёте переписку.')
        return

    # извлечение username выбранного пользователя
    username = message.text.split('Начать чат с ')[1]
    # поиск выбранного пользователя в базе данных
    cursor.execute('SELECT id, name, age, sex FROM userec WHERE nick = ?', (username,))
    user = cursor.fetchone()

    if user:
        chat_initiator_id = message.chat.id
        chat_receiver_id = user[0]

        chat_requests[chat_receiver_id] = chat_initiator_id
        keyboard = types.InlineKeyboardMarkup()
        accept_button = types.InlineKeyboardButton("Принять 😊", callback_data=f"accept_{chat_receiver_id}")
        decline_button = types.InlineKeyboardButton("Отклонить 🤬", callback_data=f"decline_{chat_receiver_id}")
        keyboard.add(accept_button, decline_button)

        # получение информации об инициаторе чата
        cursor.execute('SELECT name, age, sex FROM userec WHERE id = ?', (chat_initiator_id,))
        initiator = cursor.fetchone()

        if initiator:
            initiator_name = initiator[0]
            initiator_age = initiator[1]
            initiator_sex = initiator[2]

            # формирование сообщения с информацией о пользователе
            user_info = f"Пользователь {initiator_name} хочет начать чат с вами.\n\n"
            user_info += f"Возраст: {initiator_age}\n"
            user_info += f"Пол: {initiator_sex}\n"

            # отправка сообщения с клавиатурой второму пользователю
            bot.send_message(chat_receiver_id, user_info + "Принять или отклонить?", reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id, 'Инициатор чата не найден.')
    else:
        bot.send_message(message.chat.id, 'Выбранный пользователь не найден.')

# обработчик для принятия запроса на чат
@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_'))
def accept_callback(call):
    chat_receiver_id = int(call.data.split('_')[1])
    if chat_receiver_id in active_chats:
        bot.send_message(chat_receiver_id, f'Пользователь {bot.get_chat(chat_receiver_id).username} уже ведёт переписку.')
        return
    if chat_receiver_id in chat_requests:
        chat_initiator_id = chat_requests[chat_receiver_id]

        # добавление участников в активный чат
        active_chats[chat_initiator_id] = []
        active_chats[chat_receiver_id] = []

        # сохранение связи между участниками чата
        connections[chat_initiator_id] = chat_receiver_id
        connections[chat_receiver_id] = chat_initiator_id

        # удаление запроса на чат
        del chat_requests[chat_receiver_id]

        receiver_nickname = "@" + bot.get_chat(chat_receiver_id).username
        bot.send_message(chat_initiator_id, f'Ваш запрос на чат с пользователем {receiver_nickname} принят. Приятного общения🥰.')
        
        initiator_nickname = "@" + bot.get_chat(chat_initiator_id).username
        if receiver_nickname != initiator_nickname:
            bot.send_message(chat_receiver_id, f'Вы приняли запрос на чат с {initiator_nickname}. Приятного общения🥰.')
    else:
        bot.send_message(chat_receiver_id, 'Нет активных запросов на чат.')

# обработчик для отклонения запроса на чат
@bot.callback_query_handler(func=lambda call: call.data.startswith('decline_'))
def decline_callback(call):
    chat_receiver_id = int(call.data.split('_')[1])
    if chat_receiver_id in active_chats:
        bot.send_message(chat_receiver_id, f'Пользователь {bot.get_chat(chat_receiver_id).username} уже ведёт переписку.')
        return
    if chat_receiver_id in chat_requests:
        chat_initiator_id = chat_requests[chat_receiver_id]

        # удаление запроса на чат
        del chat_requests[chat_receiver_id]

        # сообщение инициатору чата об отклонении
        bot.send_message(chat_initiator_id, f'Ваш запрос на чат с пользователем {bot.get_chat(chat_receiver_id).username} отклонен.')
        bot.send_message(chat_receiver_id, 'Вы отклонили запрос на чат.')
    else:
        bot.send_message(chat_receiver_id, 'Нет активных запросов на чат.')

# установка соединения с базой данных
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()

# создание таблицы в базе данных, если она не существует
cursor.execute('CREATE TABLE IF NOT EXISTS userec (id INTEGER PRIMARY KEY, nick TEXT, name TEXT, age INTEGER, sex TEXT, interest1 TEXT, interest2 TEXT, interest3 TEXT)')

# обработчик команды /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    connections[message.chat.id] = None
    bot.send_message(message.chat.id, 'Привет! Для начала регистрации введи команду /register. Справка по коммандам бота вызывается командой /help.')

# обработчик команды /register
@bot.message_handler(commands=['register'])
def start_registration(message):
    connections[message.chat.id] = None
    bot.send_message(message.chat.id, 'Начинаем заполнение анкеты.\nКак тебя зовут?')
    bot.register_next_step_handler(message, get_name)

# обработчик для получения имени пользователя
def get_name(message):
    # сохранение имени пользователя в базе данных
    usrname = "@" + message.from_user.username
    try:
        cursor.execute('INSERT INTO userec (id) VALUES (?)', (message.chat.id,))
    except sqlite3.IntegrityError:
        pass
    cursor.execute('UPDATE userec SET nick = ? WHERE id = ?', (usrname, message.chat.id))
    cursor.execute('UPDATE userec SET name = ? WHERE id = ?', (message.text, message.chat.id))
    conn.commit()

    # запрос возраста пользователя
    bot.send_message(message.chat.id, 'Сколько тебе лет?')
    bot.register_next_step_handler(message, get_age)

# обработчик для получения возраста пользователя
def get_age(message):
    # сохранение возраста пользователя в базе данных
    cursor.execute('UPDATE userec SET age = ? WHERE id = ?', (message.text, message.chat.id))
    conn.commit()

    # запрос пола пользователя
    keyboard = types.ReplyKeyboardMarkup(row_width=2)
    male_button = types.KeyboardButton('Мужской👨')
    female_button = types.KeyboardButton('Женский👩')
    keyboard.add(male_button, female_button) ## добавление кнопок выбора пола
    bot.send_message(message.chat.id, 'Укажи свой пол:', reply_markup=keyboard)
    bot.register_next_step_handler(message, get_sex)

# обработчик для получения пола пользователя
def get_sex(message):
    # сохранение пола пользователя в базе данных
    cursor.execute('UPDATE userec SET sex = ? WHERE id = ?', (message.text, message.chat.id))
    conn.commit()

    remove_keyboard = types.ReplyKeyboardRemove()

    # запрос интересов пользователя
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
    interest1_button = types.KeyboardButton('Чтение📖')
    interest2_button = types.KeyboardButton('Видеоигры🎮')
    interest3_button = types.KeyboardButton('Спорт⚽🏀')
    done_button = types.KeyboardButton('Готово')
    keyboard.add(interest1_button, interest2_button, interest3_button, done_button)

    bot.send_message(message.chat.id, 'Укажи свои интересы (выбери несколько):', reply_markup=keyboard)
    bot.register_next_step_handler(message, handle_interests, [])

def handle_interests(message, interests):
    if message.text == 'Готово':
        # сортировка и сохранение интересов в базе данных
        sorted_interests = sorted(interests, key=lambda x: x.lower(), reverse=True)
        interest1 = None
        interest2 = None
        interest3 = None

        for interest in sorted_interests:
            if interest == 'Видеоигры🎮':
                interest1 = interest
            elif interest == 'Чтение📖':
                interest2 = interest
            elif interest == 'Спорт⚽🏀':
                interest3 = interest

        cursor.execute('UPDATE userec SET interest1 = ?, interest2 = ?, interest3 = ? WHERE id = ?', (interest1, interest2, interest3, message.chat.id))
        conn.commit()

        # завершение регистрации
        bot.send_message(message.chat.id, 'Регистрация завершена. Спасибо!', reply_markup=types.ReplyKeyboardRemove())
        search_button = types.KeyboardButton('Поиск🔍')
        search_keyboard = types.ReplyKeyboardMarkup(row_width=1)
        search_keyboard.add(search_button)
        bot.send_message(message.chat.id, 'Теперь вы можете найти подходящих собеседников на основе выбранных вами интересов!', reply_markup=search_keyboard)
    else:
        interests.append(message.text)
        # вывод следующего интереса
        next_interest_keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=True)
        next_interest_keyboard.add(types.KeyboardButton('Чтение📖'), types.KeyboardButton('Видеоигры🎮'), types.KeyboardButton('Спорт⚽🏀'), types.KeyboardButton('Готово'))
        bot.send_message(message.chat.id, 'Выбери следующий интерес или нажми "Готово"', reply_markup=next_interest_keyboard)
        bot.register_next_step_handler(message, handle_interests, interests)

# обработчик для поиска собеседников
def handle_match(message):
    cursor.execute('SELECT interest1, interest2, interest3 FROM userec WHERE id = ?', (message.chat.id,))
    interests = cursor.fetchone()

    if interests:
        cursor.execute('SELECT id, nick, name, age, sex FROM userec WHERE id != ? AND ((interest1 = ? OR interest2 = ? OR interest3 = ?) OR (interest1 = ? OR interest2 = ? OR interest3 = ?) OR (interest1 = ? OR interest2 = ? OR interest3 = ?))',
                       (message.chat.id, interests[0], interests[0], interests[0], interests[1], interests[1], interests[1], interests[2], interests[2], interests[2]))
        matches = cursor.fetchall()

        if matches:
            response = 'Найдены подходящие пользователи:\n'
            for match in matches:
                info = f'ID: {match[0]}\nUsername: {match[1]}\nИмя: {match[2]}\nВозраст: {match[3]}\nПол: {match[4]}'
                response += info + '\n\n'

            start_chat_keyboard = types.ReplyKeyboardMarkup(row_width=1)
            for match in matches:
                start_chat_button = types.KeyboardButton(f'Начать чат с {match[1]}')
                start_chat_keyboard.add(start_chat_button)

            bot.send_message(message.chat.id, response, reply_markup=start_chat_keyboard)
        else:
            bot.send_message(message.chat.id, 'Совместимые собеседники не найдены😭.')
    else:
        bot.send_message(message.chat.id, 'Сначала завершите регистрацию командой /register')

# обработчик команды /match
@bot.message_handler(commands=['match'])
def command_match(message):
    handle_match(message)

# обработчик для кнопки "Поиск🔍"
@bot.message_handler(func=lambda message: message.text == 'Поиск🔍')
def text_match(message):
    handle_match(message)

# обработчик команды /help
@bot.message_handler(commands=['help'])
def show_help(message):
    help_text = '''
    Этот бот предоставляет возможность поиска собеседников на основе их интересов😘
    
    Команды:
    /start - старт
    /register - регистрация
    /match - поиск собеседника по интересам
    /stop - остановить общение
    /help - помощь
    /about - о боте
    '''
    bot.send_message(message.chat.id, help_text)

# обработчик команды /about
@bot.message_handler(commands=['about'])
def show_about(message):
    about_text = '''
    👨‍💻Разработчик: alexl2004 (GitHub: 8alexl) 😎
    Версия от 22.05.2023
    '''
    bot.send_message(message.chat.id, about_text)

# запуск бота
bot.polling()