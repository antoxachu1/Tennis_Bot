
import os
import json
import datetime
import google.auth
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, filters, CallbackContext

# Укажите путь к файлу с учетными данными
CREDENTIALS_FILE = 'c:/bot/google_token.json'
TOKEN_FILE = 'c:/bot/telegram_token.json'
SCOPES = ['https://www.googleapis.com/auth/calendar']
TOKEN = '7151449138:AAF9aomg90CgtnnJd5-xejoBHxPoxJTrgx0'

# ID календаря
CALENDAR_ID = 'primary'

# Константы для состояний разговора
SELECT_TIME, CONFIRMATION = range(2)

def get_calendar_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    service = build('calendar', 'v3', credentials=creds)
    return service

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Привет! Я ваш бот для записи на теннисный корт. Используйте /book для записи.')

async def help_command(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text('Доступные команды:\n/book - Записаться на корт\n/schedule - Посмотреть расписание')

async def book(update: Update, context: CallbackContext) -> int:
    reply_keyboard = [['10:00', '11:00', '12:00'], ['13:00', '14:00', '15:00']]
    await update.message.reply_text(
        'Пожалуйста, выберите время:',
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return SELECT_TIME

async def select_time(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    selected_time = update.message.text
    context.user_data['selected_time'] = selected_time

    service = get_calendar_service()
    selected_datetime = datetime.datetime.combine(datetime.date.today(), datetime.datetime.strptime(selected_time, '%H:%M').time())
    events_result = service.events().list(calendarId=CALENDAR_ID, timeMin=selected_datetime.isoformat() + 'Z',
                                          timeMax=(selected_datetime + datetime.timedelta(hours=1)).isoformat() + 'Z',
                                          singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])

    if events:
        await update.message.reply_text(f'Извините, {selected_time} уже занято. Пожалуйста, выберите другое время.')
        return SELECT_TIME
    else:
        await update.message.reply_text(f'Вы выбрали {selected_time}. Подтвердите запись? (да/нет)')
        return CONFIRMATION

async def confirm(update: Update, context: CallbackContext) -> int:
    user = update.message.from_user
    confirmation = update.message.text.lower()

    if confirmation == 'да':
        selected_time = context.user_data['selected_time']
        selected_datetime = datetime.datetime.combine(datetime.date.today(), datetime.datetime.strptime(selected_time, '%H:%M').time())
        event = {
            'summary': f'Бронирование теннисного корта: {user.first_name}',
            'start': {
                'dateTime': selected_datetime.isoformat(),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': (selected_datetime + datetime.timedelta(hours=1)).isoformat(),
                'timeZone': 'UTC',
            },
        }
        service = get_calendar_service()
        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        await update.message.reply_text(f'Вы успешно записались на {selected_time}.')
        return ConversationHandler.END
    else:
        await update.message.reply_text('Запись отменена.')
        return ConversationHandler.END

async def schedule_command(update: Update, context: CallbackContext) -> None:
    service = get_calendar_service()
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(calendarId=CALENDAR_ID, timeMin=now,
                                          maxResults=10, singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])

    if not events:
        await update.message.reply_text('Расписание пусто.')
    else:
        schedule_text = 'Текущее расписание:\n'
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            schedule_text += f"{start}: {event['summary']}\n"
        await update.message.reply_text(schedule_text)

async def cancel(update: Update, context: CallbackContext) -> int:
    await update.message.reply_text('Запись отменена.')
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('book', book)],
        states={
            SELECT_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_time)],
            CONFIRMATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("schedule", schedule_command))
    application.add_handler(conv_handler)

    application.run_polling()

if __name__ == '__main__':
    main()
