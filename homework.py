import logging
import os
import time

from http import HTTPStatus

import requests

from dotenv import load_dotenv
import telegram

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='program.log',
    level=logging.DEBUG)

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


def check_tokens():
    """Проверяет доступность переменных окружения."""
    required_tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in required_tokens:
        if token is None:
            logger.critical(f'Отсутствует переменная окружения {token}.')
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug('Сообщение отправлено.')
    except Exception:
        logger.error('Ошибка отправки сообщения в Telegram.')
        raise Exception('Ошибка отправки сообщения в Telegram.')


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params)
        if homework_statuses.status_code != HTTPStatus.OK:
            logger.error(f'{ENDPOINT} недоступен.')
            raise ValueError(f'Сервер недоступен. Код ответа '
                             f'{homework_statuses.status_code}.')
    except requests.exceptions.RequestException as request_error:
        raise ConnectionError(f'Ошибка {request_error} при попытке запроса.')
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logger.info(
            'Некорректный тип данных: ответ API должен иметь тип "dict".'
        )
        raise TypeError(
            'Некорректный тип данных: ответ API должен иметь тип "dict".'
        )
    if 'homeworks' not in response:
        logger.info(
            'В полученном ответе отсутсвует ключ "homeworks".'
        )
        raise KeyError(
            'В полученном ответе отсутсвует ключ "homeworks".'
        )
    if not isinstance(response['homeworks'], list):
        logger.info(
            'Тип данных "homeworks" должен иметь тип "list".'
        )
        raise TypeError(
            'Некорректный тип данных: "homeworks" должен иметь тип "list".'
        )
    return response['homeworks']


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        logger.error('Некорректный статус домашней работы.')
        raise KeyError('Некорректный статус домашней работы.')
    if 'homework_name' not in homework:
        logger.error('Отсутствует ключ "homework_name"')
        raise KeyError(
            'В полученной информации отсутствует ключ "homework_name".')
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Ошибка в переменных окружения.')
        raise Exception('Ошибка в переменных окружения.')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_message = None
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            timestamp = response.get('current_date')
            if homework != []:
                message = parse_status(homework[0])
                if message != previous_message:
                    send_message(bot, message)
                    previous_message = message
        except Exception as error:
            message = f'Сбой в работе программы: {error}.'
            logger.error(f'{error}')
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
