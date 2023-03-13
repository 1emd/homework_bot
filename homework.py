import logging
import os
import sys
import time

from http import HTTPStatus

import requests
import telegram

from dotenv import load_dotenv

load_dotenv()

EMPTY_REQUIRED_TOKENS = 'Отсутствует переменная окружения {token}.'
ERROR_SENDING_MESSAGE = 'Ошибка отправки сообщения в Telegram.'
MESSAGE_SENT = 'Сообщение отправлено.'
ENDPOINT_UNAVAILABLE = '{ENDPOINT} недоступен.'
SERVER_UNAVAILABLE = 'Сервер недоступен. Код ответа '
REQUEST_ERROR = 'Ошибка {request_error} при попытке запроса.'
INVALID_API_RESPONSE_TYPE = 'Некорректный тип данных: ' \
                            'ответ API должен иметь тип "dict".'
MISSING_HOMEWORKS_KEY = 'В полученном ответе отсутсвует ключ "homeworks".'
INVALID_HOMEWORKS_TYPE = 'Некорректный тип данных: '\
                         '"homeworks" должен иметь тип "list".'
INVALID_HOMEWORK_STATUS = 'Некорректный статус домашней работы.'
MISSING_HOMEWORK_NAME_KEY = 'Отсутствует ключ "homework_name".'
CHECK_STATUS_CHANGED = 'Изменился статус проверки работы '\
                       '"{homework_name}". {verdict}'
ERROR_REQUIRED_TOKENS = 'Ошибка в переменных окружения.'
PROGRAM_STOPPED = 'Программа остановлена.'
PROGRAM_FAILURE = 'Сбой в работе программы: {error}.'
MAIN_FUNCTION_ERROR = '{error}'

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


def check_tokens():
    """Проверяет доступность переменных окружения."""
    required_tokens = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
    global_dict = globals()
    for token in required_tokens:
        if token not in global_dict or global_dict[token] is None:
            logging.critical(EMPTY_REQUIRED_TOKENS.format(token=token))
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception:
        logging.error(ERROR_SENDING_MESSAGE)
        raise Exception(ERROR_SENDING_MESSAGE)
    else:
        logging.debug(MESSAGE_SENT)


def get_api_answer(timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params)
        if homework_statuses.status_code != HTTPStatus.OK:
            logging.error(ENDPOINT_UNAVAILABLE.format(ENDPOINT=ENDPOINT))
            raise ValueError(SERVER_UNAVAILABLE,
                             f'{homework_statuses.status_code}.')
    except requests.exceptions.RequestException as request_error:
        raise ConnectionError(REQUEST_ERROR.format(
            request_error=request_error))
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        logging.info(INVALID_API_RESPONSE_TYPE)
        raise TypeError(INVALID_API_RESPONSE_TYPE)
    if 'homeworks' not in response:
        logging.info(MISSING_HOMEWORKS_KEY)
        raise KeyError(MISSING_HOMEWORKS_KEY)
    if not isinstance(response['homeworks'], list):
        logging.info(INVALID_HOMEWORKS_TYPE)
        raise TypeError(INVALID_HOMEWORKS_TYPE)
    return response['homeworks']


def parse_status(homework):
    """Извлекает из информации о конкретной домашней работе статус работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        logging.error(INVALID_HOMEWORK_STATUS)
        raise KeyError(INVALID_HOMEWORK_STATUS)
    if 'homework_name' not in homework:
        logging.error(MISSING_HOMEWORK_NAME_KEY)
        raise KeyError(
            MISSING_HOMEWORK_NAME_KEY)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return CHECK_STATUS_CHANGED.format(
        homework_name=homework_name, verdict=verdict)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical(ERROR_REQUIRED_TOKENS)
        sys.exit(PROGRAM_STOPPED)
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_message = None
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            timestamp = response.get('current_date')
            if homework:
                message = parse_status(homework[0])
                if message != previous_message:
                    send_message(bot, message)
                    previous_message = message
        except Exception as error:
            message = PROGRAM_FAILURE.format(error=error)
            logging.error(MAIN_FUNCTION_ERROR.format(error=error))
            send_message(bot, message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.DEBUG,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('program.log', encoding='UTF-8')]
    )
    logging.getLogger().handlers[0].setLevel(logging.INFO)

    main()
