import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
import telegram


load_dotenv()


PRACTICUM_TOKEN = os.getenv('SECRET_PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('SECRET_TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('SECRET_TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s, %(funcName)s, %(lineno)d')
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Функция проверки наличия токена и чат id телеграмма."""
    logger.debug('Проверка токеннов')
    tokens = (PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN)
    if not all(tokens):
        logger.critical('Все токены не найдены')
        sys.exit('Бот закончил работу проверьте tokens')
    logger.debug('Проверка tokens успешна')


def send_message(bot, message):
    """Отправляет сообщение `message` в указанный telegram-чат."""
    logger.debug('Попытка отправить сообщение в Telegram.')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except telegram.TelegramError as error:
        logger.error(
            f'Не удалось отправить сообщение в Telegram. {error}')
    logger.debug('Сообщение в Telegram успешно отправлено.')


def get_api_answer(current_timestamp):
    """запрос статуса домашней работы."""
    timestamp = current_timestamp or int(time.time())
    params_request = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }
    message = ('Начало запроса к API. Запрос: {url}, {params}.'
               ).format(**params_request)
    logger.debug(message)
    try:
        homework_statuses = requests.get(**params_request)
    except requests.RequestException as error:
        raise ConnectionError(f'запрос не может быть выполнен, {error}'
                              f'Причина: {homework_statuses.reason}.'
                              f'Текст: {homework_statuses.text}.'
                              )
    if homework_statuses.status_code != HTTPStatus.OK:
        message = ('не успешное получение API. {url}, {params}.'
                   ).format(**params_request)
        logger.error(message)
        raise ValueError(
            f'Недоступен {ENDPOINT} , код {homework_statuses.status_code}')
    else:
        message = ('успешное получение API. {url}, {params}.'
                   ).format(**params_request)
        logger.debug(message)
        return homework_statuses.json()


def check_response(response):
    """Функция проверки корректности ответа API Яндекс.Практикум."""
    logger.debug('Проверка ответа API на корректность')
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является dict')
    if 'homeworks' not in response or 'current_date' not in response:
        raise KeyError('Нет ключа homeworks в ответе API')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('homeworks не является list')
    return homeworks


def parse_status(homework):
    """Функция, проверяющая статус домашнего задания."""
    logger.debug('Проводим проверки и извлекаем статус работы')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if 'homework_name' not in homework:
        raise KeyError('Нет ключа homework_name в ответе API ')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы - {homework_status}')
    return ('Изменился статус проверки работы "{homework_name}". {verdict}'
            ).format(homework_name=homework_name,
                     verdict=HOMEWORK_VERDICTS[homework_status])


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD
    logger.info('Бот начал работу')
    last_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            timestamp = response.get(
                'current_date', int(time.time())
            )
            if homeworks:
                message = parse_status(homeworks[0])
            else:
                message = 'Нет новых статусов.'
            if message != last_message:
                send_message(bot, message)
                last_message = message
            else:
                logger.debug(message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message, exc_info=True)
            if message != last_message:
                send_message(bot, message)
                last_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
