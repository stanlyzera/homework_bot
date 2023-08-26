import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv


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

logging.basicConfig(
    level=logging.DEBUG,
    filename='program.log',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)


class IncorrectStatusError(Exception):
    """Исключение для некорректного статуса ответа API."""

    pass


def check_tokens():
    """Проверка наличия токенов."""
    if PRACTICUM_TOKEN and TELEGRAM_CHAT_ID and TELEGRAM_TOKEN and ENDPOINT:
        return True
    else:
        logging.critical('Не все необходимые токены установлены.')
        return False


def send_message(bot, message):
    """Отправка сообщения пользователю TELEGRAM_CHAT_ID с статусом работы."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Сообщение успешно отправлено: {message}')
    except Exception as error:
        logging.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Проверка соединения с API."""
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=timestamp)
        status_code = response.status_code
        if status_code != HTTPStatus.OK:
            raise IncorrectStatusError(status_code)
        return response.json()
    except requests.RequestException as error:
        logging.error(f'Ошибка при запросе к API: {error}')


def check_response(response):
    """Проверка формата ответа response согласно документации API."""
    if isinstance(response, dict) and \
       isinstance(response.get('homeworks'), list):
        return response['homeworks'][0]
    else:
        logging.error('В ответе отсутствует нужная информация')
        raise TypeError('В ответе отсутствует нужная информация')


def parse_status(homework):
    """
    Проверка корректности статуса homework.
    В соответствии с документацией API.
    """
    try:
        if homework['homework_name']:
            if homework.get('status') in HOMEWORK_VERDICTS:
                homework_name = homework.get('homework_name')
                verdict = HOMEWORK_VERDICTS[homework.get('status')]
                return (
                    f'Изменился статус проверки работы "{homework_name}". '
                    f'{verdict}'
                )
            else:
                status = homework.get('status')
                logging.error(f'Неизвестный статус домашней работы: {status}')
                raise Exception(
                    f'Неизвестный статус домашней работы: {status}'
                )
    except KeyError("`homework_name`"):
        logging.error('Отсутствие ключа homework_name')
        return


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Не все необходимые токены установлены.')
        return

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = {'from_date': int(time.time()) - RETRY_PERIOD}

    while True:
        try:
            response = get_api_answer(timestamp)
            if response:
                homework = check_response(response)
                if homework:
                    message = parse_status(homework)
                    if message:
                        send_message(bot, message)
        except Exception as error:
            logging.error(f'Сбой в работе программы: {error}')
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()
