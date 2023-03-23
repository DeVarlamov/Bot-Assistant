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
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Функция проверки наличия токена и чат id телеграмма."""
    if PRACTICUM_TOKEN is None:
        logging.critical('PRACTICUM_TOKEN не найден')
        return sys.exit('бот завершил работу')
    if TELEGRAM_CHAT_ID is None:
        logging.critical('TELEGRAM_CHAT_ID не найден')
        return sys.exit('бот завершил работу')
    if TELEGRAM_TOKEN is None:
        logging.critical('TELEGRAM_TOKEN не найден')
        return sys.exit('бот завершил работу')
    return True


def send_message(bot, message):
    """Отправляет сообщение `message` в указанный telegram-чат."""
    logger.debug('Попытка отправить сообщение в Telegram.')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение в Telegram успешно отправлено.')
    except telegram.TelegramError as error:
        logger.error(
            f'Не удалось отправить сообщение в Telegram. {error}')


def get_api_answer(current_timestamp):
    """запрос статуса домашней работы."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=params)
    except requests.RequestException as error:
        raise ConnectionError(f'запрос не может быть выполнен, {error}')  #тут что то надо
    if homework_statuses.status_code == HTTPStatus.OK:
        logger.info('успешное получение Эндпоинта')  # тут что то надо
        homework = homework_statuses.json()
        return homework
    elif homework_statuses.status_code == HTTPStatus.REQUEST_TIMEOUT:
        raise SystemError(f'Ошибка код {homework_statuses.status_code}')
    elif homework_statuses.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
        raise SystemError(f'Ошибка код {homework_statuses.status_code}')
    else:
        raise SystemError(
            f'Недоступен Эндпоинт, код {homework_statuses.status_code}')


def check_response(response):
    """Функция проверки корректности ответа API Яндекс.Практикум."""
    try:
        timestamp = response['current_date']
    except KeyError:
        logging.error(
            'Ключ current_date в ответе API Яндекс.Практикум отсутствует'
        )
    try:
        homeworks = response['homeworks']
    except KeyError:
        logging.error(
            'Ключ homeworks в ответе API Яндекс.Практикум отсутствует'
        )
    if isinstance(timestamp, int) and isinstance(homeworks, list):
        return homeworks
    else:
        raise TypeError


def parse_status(homework):
    """Функция, проверяющая статус домашнего задания."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')

    if homework_name is not None and homework_status is not None:
        if homework_status in HOMEWORK_VERDICTS:
            verdict = HOMEWORK_VERDICTS.get(homework_status)
            return ('Изменился статус проверки '
                    + f'работы "{homework_name}". {verdict}')
        else:
            raise SystemError('неизвестный статус')
    else:
        raise KeyError('нет нужных ключей в словаре')


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD

    while True:
        try:
            if type(timestamp) is not int:
                raise SystemError('Формат времени не INT')
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            quantity_of_works = len(homeworks)

            while quantity_of_works > 0:
                message = parse_status(homeworks[quantity_of_works - 1])
                send_message(bot, message)
                quantity_of_works -= 1
            timestamp = int(time.time())
            time.sleep(RETRY_PERIOD)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
