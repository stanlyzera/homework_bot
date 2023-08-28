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
    missing_tokens = [i for i in required_tokens if not globals()[i]]
    if missing_tokens:
        logging.critical(f'Не хватает следующих'
                         f'токенов: {", ".join(missing_tokens)}')
        sys.exit(1)
    return True


def send_message(bot, message):
    """Отправка сообщения пользователю TELEGRAM_CHAT_ID с статусом работы."""
    try:
        logging.debug(f'Отправление сообщения: {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение успешно отправлено: {message}')
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Проверка соединения с API."""
    timestamp = {'from_date': timestamp}
    try:
        logging.debug('Отправление запроса')
        response = requests.get(ENDPOINT, headers=HEADERS, params=timestamp)
        status_code = response.status_code
    except requests.RequestException as error:
        logging.error(f'Ошибка при запросе к API: {error}')
    if status_code != HTTPStatus.OK:
        raise IncorrectStatusError(f'При отправке запроса c params {timestamp}'
                                   f'был получен {status_code}')
    logging.debug(f'Ответ на запрос успешно получен: {response}')
    return response.json()


def check_response(response):
    """Проверка формата ответа response согласно документации API."""
    logging.debug(f'Начало проверки ответа response: {response}')
    if isinstance(response, dict):
        if isinstance(response.get('homeworks'), list):
            logging.debug('Успешное завершение проверки')
            return response
        else:
            logging.error(f'{response.get("homeworks")}, не является списком')
            raise TypeError('Неверный формат ответа')
    else:
        logging.error(f'{response} не является словарем]')
        raise TypeError('Неверный формат ответа')


def parse_status(homework):
    """
    Проверка корректности статуса homework.
    В соответствии с документацией API.
    """
    logging.debug('Начало выполнение проверки статуса homework')
    if 'homework_name' in homework:
        homework_name = homework['homework_name']
        status = homework.get('status')
        if status in HOMEWORK_VERDICTS:
            verdict = HOMEWORK_VERDICTS[status]
            return (
                f'Изменился статус проверки работы "{homework_name}". '
                f'{verdict}'
            )
        else:
            logging.error(f'Неизвестный статус домашней работы: {status}')
            raise ValueError(f'Неизвестный статус домашней работы: {status}')
    else:
        logging.error('В словаре отсутствует ключ homework_name')
        raise KeyError('В словаре отсутствует ключ homework_name')


def main():
    """Основная логика работы бота."""
    check_tokens()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD
    last_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            new_homeworks = check_response(response)
            if new_homeworks['homeworks']:
                homework = new_homeworks['homeworks'][0]
                message = parse_status(homework)
                if message != last_message:
                    send_message(bot, message)
                    last_message = message
            else:
                logging.debug('Новых статусов нет')
        except telegram.TelegramError as telegram_error:
            logging.error(f'Ошибка при отправке сообщения '
                          f'в Telegram: {telegram_error}')
        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
            with suppress(telegram.TelegramError):
                send_message(bot, f'Произошла ошибка: {error}')
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - '
                                  '%(message)s - %(name)s - %(lineno)d')
    stream_handler.setFormatter(formatter)

    logger = logging.getLogger(__name__)
    logger.addHandler(stream_handler)

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s - %(name)s'
    )
    main()
