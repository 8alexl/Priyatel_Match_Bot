import os
import telebot
from telebot import types
from dotenv import load_dotenv
import sqlite3

# загрузка токена из переменных окружения
load_dotenv()
bot = telebot.TeleBot(os.getenv('TELEGRAM_BOT_TOKEN'))

# словари для управления соединениями и активными чатами
chat_requests = {}
active_chats = {}
connections = {}

# класс для представления сообщений в чате
class ChatMessage:
    def __init__(self, sender, text):
        self.sender = sender
        self.text = text

# подключение к базе данных
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()

# создание таблицы, если она не существует
cursor.execute('''CREATE TABLE IF NOT EXISTS userec (
    id INTEGER PRIMARY KEY, 
    nick TEXT, 
    name TEXT, 
    age INTEGER, 
    sex TEXT, 
    interest1 TEXT, 
    interest2 TEXT, 
    interest3 TEXT)''')
conn.commit()

# команда для остановки текущего чата
@bot.message_handler(commands=['stop'])
def stop_chat(message):
    chat_id = message.chat.id
    if chat_id in active_chats:
        partner_chat_id = connections.get(chat_id)

        # удаление активного чата и связи между собеседниками
        del active_chats[chat_id]
        if partner_chat_id:
            del active_chats[partner_chat_id]
            connections[partner_chat_id] = None

        connections[chat_id] = None

        # уведомление пользователей об остановке чата
        bot.send_message(chat_id, 'Переписка остановлена. Для начала новой переписки введи команду /match')
        if partner_chat_id:
            bot.send_message(partner_chat_id, 'Переписка остановлена. Для начала новой переписки введи команду /match')

# обработчик сообщений в активных чатах
@bot.message_handler(func=lambda message: message.chat.id in active_chats)
def handle_messages(message):
    chat_id = message.chat.id
    current_chat = active_chats[chat_id]

    if message.text not in ['/stop', '/help']:
        sender = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        current_chat.append(ChatMessage(sender, message.text))

        # отправка сообщения собеседнику
        if chat_id in connections and connections[chat_id]:
            receiver_chat_id = connections[chat_id]
            receiver_message = f"{sender}: {message.text}"
            bot.send_message(receiver_chat_id, receiver_message)
        else:
            bot.send_message(chat_id, 'Ожидание собеседника...')
    elif message.text == '/help':
        show_help(message)
    elif message.text == '/stop':
        stop_chat(message)

# обработчик для запроса начала чата с другим пользователем
@bot.message_handler(func=lambda message: message.text.startswith('Начать чат с'))
def start_chat(message):
    chat_initiator_id = message.chat.id
    if chat_initiator_id in active_chats:
        bot.send_message(chat_initiator_id, 'В данный момент вы уже ведёте переписку.')
        return

    username = message.text.split('Начать чат с ')[1]
    cursor.execute('SELECT id, name, age, sex FROM userec WHERE nick = ?', (username,))
    user = cursor.fetchone()

    if user:
        chat_receiver_id = user[0]
        chat_requests[chat_receiver_id] = chat_initiator_id
        
        # создание клавиатуры для принятия/отклонения чата
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton("Принять 😊", callback_data=f"accept_{chat_receiver_id}"),
            types.InlineKeyboardButton("Отклонить 🤬", callback_data=f"decline_{chat_receiver_id}")
        )

        # информация об инициаторе чата
        cursor.execute('SELECT name, age, sex FROM userec WHERE id = ?', (chat_initiator_id,))
        initiator = cursor.fetchone()

        if initiator:
            user_info = f"Пользователь {initiator[0]} хочет начать чат с вами.\nВозраст: {initiator[1]}\nПол: {initiator[2]}\nПринять или отклонить?"
            bot.send_message(chat_receiver_id, user_info, reply_markup=keyboard)
        else:
            bot.send_message(chat_initiator_id, 'Инициатор чата не найден.')
    else:
        bot.send_message(chat_initiator_id, 'Выбранный пользователь не найден.')

# обработчик принятия запроса на чат
@bot.callback_query_handler(func=lambda call: call.data.startswith('accept_'))
def accept_callback(call):
    chat_receiver_id = int(call.data.split('_')[1])
    
    if chat_receiver_id in chat_requests:
        chat_initiator_id = chat_requests.pop(chat_receiver_id)
        
        # устанавка соединения
        active_chats[chat_initiator_id] = []
        active_chats[chat_receiver_id] = []
        connections[chat_initiator_id] = chat_receiver_id
        connections[chat_receiver_id] = chat_initiator_id

        initiator_username = f"@{bot.get_chat(chat_initiator_id).username}"
        receiver_username = f"@{bot.get_chat(chat_receiver_id).username}"
        
        # уведомление пользователей
        bot.send_message(chat_initiator_id, f'Ваш запрос на чат с пользователем {receiver_username} принят. Приятного общения🥰.')
        bot.send_message(chat_receiver_id, f'Вы приняли запрос на чат с {initiator_username}. Приятного общения🥰.')

# обработчик отклонения запроса на чат
@bot.callback_query_handler(func=lambda call: call.data.startswith('decline_'))
def decline_callback(call):
    chat_receiver_id = int(call.data.split('_')[1])
    
    if chat_receiver_id in chat_requests:
        chat_initiator_id = chat_requests.pop(chat_receiver_id)

        # уведомляем пользователей об отказе
        bot.send_message(chat_initiator_id, f'Ваш запрос на чат с пользователем {bot.get_chat(chat_receiver_id).username} отклонен.')
        bot.send_message(chat_receiver_id, 'Вы отклонили запрос на чат.')

# обработчики для команд /start и /register
@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(message.chat.id, 'Привет! Для начала регистрации введи команду /register. Справка по командам - /help.')

@bot.message_handler(commands=['register'])
def start_registration(message):
    bot.send_message(message.chat.id, 'Начинаем заполнение анкеты.\nКак тебя зовут?')
    bot.register_next_step_handler(message, get_name)

# получение и сохранение данных пользователя
def get_name(message):
    username = f"@{message.from_user.username}"
    cursor.execute('INSERT OR IGNORE INTO userec (id) VALUES (?)', (message.chat.id,))
    cursor.execute('UPDATE userec SET nick = ?, name = ? WHERE id = ?', (username, message.text, message.chat.id))
    conn.commit()
    bot.send_message(message.chat.id, 'Сколько тебе лет?')
    bot.register_next_step_handler(message, get_age)

def get_age(message):
    if message.text.isdigit() and 10 <= int(message.text) <= 100:
        cursor.execute('UPDATE userec SET age = ? WHERE id = ?', (int(message.text), message.chat.id))
        conn.commit()
        keyboard = types.ReplyKeyboardMarkup(row_width=2)
        keyboard.add(types.KeyboardButton('Мужской👨'), types.KeyboardButton('Женский👩'))
        bot.send_message(message.chat.id, 'Укажи свой пол:', reply_markup=keyboard)
        bot.register_next_step_handler(message, get_sex)
    else:
        bot.send_message(message.chat.id, "Пожалуйста, укажите возраст числом (10-100 лет).")
        bot.register_next_step_handler(message, get_age)

def get_sex(message):
    cursor.execute('UPDATE userec SET sex = ? WHERE id = ?', (message.text, message.chat.id))
    conn.commit()
    request_interests(message)

def request_interests(message):
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    keyboard.add('Чтение📖', 'Видеоигры🎮', 'Спорт⚽🏀', 'Готово')
    bot.send_message(message.chat.id, 'Укажи свои интересы:', reply_markup=keyboard)
    bot.register_next_step_handler(message, handle_interests, [])

def handle_interests(message, interests):
    if message.text == 'Готово':
        cursor.execute('UPDATE userec SET interest1 = ?, interest2 = ?, interest3 = ? WHERE id = ?',
                       (interests[0] if len(interests) > 0 else None,
                        interests[1] if len(interests) > 1 else None,
                        interests[2] if len(interests) > 2 else None,
                        message.chat.id))
        conn.commit()
        bot.send_message(message.chat.id, 'Регистрация завершена. Спасибо!', reply_markup=types.ReplyKeyboardRemove())
    else:
        interests.append(message.text)
        request_interests(message)

# команда /match для поиска совпадений по интересам
@bot.message_handler(commands=['match', 'Поиск'])
def find_match(message):
    cursor.execute('SELECT interest1, interest2, interest3 FROM userec WHERE id = ?', (message.chat.id,))
    user_interests = cursor.fetchone()

    if user_interests:
        query = 'SELECT id, name FROM userec WHERE (interest1 IN (?, ?, ?) OR interest2 IN (?, ?, ?) OR interest3 IN (?, ?, ?)) AND id != ?'
        cursor.execute(query, (*user_interests, *user_interests, message.chat.id))
        matches = cursor.fetchall()

        if matches:
            bot.send_message(message.chat.id, f"Найдены подходящие пользователи:")
            for match in matches:
                bot.send_message(message.chat.id, f"Начать чат с {match[1]}")
        else:
            bot.send_message(message.chat.id, 'К сожалению, подходящих пользователей не найдено.')
    else:
        bot.send_message(message.chat.id, 'Заполните сначала свои данные с помощью /register')

# команда /help
@bot.message_handler(commands=['help'])
def show_help(message):
    help_text = '''
    Доступные команды:
    /start - Начало работы
    /register - Регистрация
    /stop - Остановить текущий чат
    /match - Поиск совпадений
    '''
    bot.send_message(message.chat.id, help_text)

# запуск бота
if __name__ == "__main__":
    bot.polling(none_stop=True)