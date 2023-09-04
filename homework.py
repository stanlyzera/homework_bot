import logging
import os
import time
import sys
from contextlib import suppress
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

from exceptions import IncorrectStatusError

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - '
                              '%(message)s - %(name)s - %(lineno)d')
stream_handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.addHandler(stream_handler)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PracToken')
TELEGRAM_TOKEN = os.getenv('TelToken')
TELEGRAM_CHAT_ID = os.getenv('TelId')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка наличия токенов."""
    required_tokens = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN',
                       'TELEGRAM_CHAT_ID', 'ENDPOINT')
    missing_tokens = [token for token in required_tokens if not globals()[token]]
    if missing_tokens:
        logger.critical(f'Не хватает следующих'
                        f'токенов: {", ".join(missing_tokens)}')
        sys.exit(1)


def send_message(bot, message):
    """Отправка сообщения пользователю TELEGRAM_CHAT_ID с статусом работы."""
    logger.debug(f'Отправление сообщения: {message}')
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logger.debug(f'Сообщение успешно отправлено: {message}')


def get_api_answer(timestamp):
    """Проверка соединения с API."""
    timestamp = {'from_date': timestamp}
    try:
        logger.debug('Отправление запроса')
        response = requests.get(ENDPOINT, headers=HEADERS, params=timestamp)
        status_code = response.status_code
    except requests.RequestException as error:
        raise ConnectionError(f'Не удалось соединиться {error}')
    if status_code != HTTPStatus.OK:
        raise IncorrectStatusError(f'При отправке запроса c params {timestamp}'
                                   f'был получен {status_code}')
    logger.debug(f'Ответ на запрос успешно получен: {response}')
    return response.json()


def check_response(response):
    """Проверка формата ответа response согласно документации API."""
    logger.debug(f'Начало проверки ответа response: {response}')
    if not isinstance(response, dict):
        raise TypeError('Ответ не является словарем')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('homeworks не является списком')
    logger.debug('Успешное завершение проверки')
    return response


def parse_status(homework):
    """
    Проверка корректности статуса homework.
    В соответствии с документацией API.
    """
    logger.debug('Начало выполнение проверки статуса homework')
    if 'homework_name' not in homework:
        raise KeyError('В словаре отсутствует ключ homework_name')
    homework_name = homework['homework_name']
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус домашней работы: {status}')
    verdict = HOMEWORK_VERDICTS[status]
    return (
        f'Изменился статус проверки работы "{homework_name}". '
        f'{verdict}'
    )


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''
    last_error_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            new_homeworks_response = check_response(response)
            new_homeworks = new_homeworks_response['homeworks']
            if new_homeworks:
                homework = new_homeworks[0]
                message = parse_status(homework)
                if message != last_message:
                    send_message(bot, message)
                    last_message = message
                else:
                    logger.debug(f'Пришло повторяющиеся сообщение {message}')
            else:
                logger.debug('Новых статусов нет')
            timestamp = int(time.time())
        except telegram.TelegramError as telegram_error:
            logger.error(f'Ошибка при отправке сообщения '
                         f'в Telegram: {telegram_error}', exc_info=True)
        except Exception as error:
            ERROR_MESSAGE = 'Сбой в работе программы:' + str(error)
            logger.error(ERROR_MESSAGE, exc_info=True)
            with suppress(telegram.TelegramError):
                if str(error) != last_error_message:
                    send_message(bot, ERROR_MESSAGE)
                    last_error_message = str(error)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
