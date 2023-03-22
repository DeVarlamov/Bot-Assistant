import logging
import os
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
logger.setLevel(logging.INFO)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter(
    '%(asctime)s, %(levelname)s, %(message)s')
handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)


def check_tokens():
    """Функция проверки наличия токена и чат id телеграмма."""
    tokens = {
        'SECRET_PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'SECRET_TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'SECRET_TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for key, value in tokens.items():
        if value is None:
            logging.error(f'{key} отсутствует')
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение `message` в указанный telegram-чат."""
    try:
        logger.debug('Попытка отправить сообщение в Telegram отправлено.')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение в Telegram успешно отправлено.')
    except Exception:
        raise logger.error('Не удалось отправить сообщение в Telegram.')


def get_api_answer(current_timestamp):
    """запрос статуса домашней работы."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=params)
    except Exception as error:
        raise SystemError(f'Ошибка получения request, {error}')
    else:
        if homework_statuses.status_code == HTTPStatus.OK:
            logger.info('успешное получение Эндпоинта')
            homework = homework_statuses.json()
            if 'error' in homework:
                raise SystemError(f'Ошибка json, {homework["error"]}')
            elif 'code' in homework:
                raise SystemError(f'Ошибка json, {homework["code"]}')
            else:
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
    if not check_tokens():
        raise logger.critical('Программа закончила работу')
    else:
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
