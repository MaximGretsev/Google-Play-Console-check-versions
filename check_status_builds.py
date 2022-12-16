from pprint import pprint
import time
import logging

import requests
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


packages_dict: dict = {}
builds_on_gp: dict = {}
compare_builds: dict = {}


def main():
    parse_id = parse_id_and_build()
    print(parse_id)
    get_partner_info = get_partner_id_and_review_builds(parse_id)
    pprint(f'Партнеры, кто был отправлен в ревью:\n{get_partner_info}')
    get_package = get_package_name(get_partner_info)
    pprint(get_package)
    gp_builds = get_build_from_gp(get_package)
    pprint(f'Версии приложения на маркете:\n{gp_builds}')
    compare = get_compare_builds(get_partner_info)
    pprint(f'Текущий статус версии:\n{compare}')
    set_build_on_mba(compare)


def parse_id_and_build():
    """

    :return: Возвращает JSON, который функция получила от MBA.
    """
    url_partner_info = "URL_WITH_PARTNERS"
    partner_info_parse = requests.get(url_partner_info)
    data_info_partner = partner_info_parse.json()
    return data_info_partner


def get_partner_id_and_review_builds(data_info_partner) -> dict:
    """
    :param data_info_partner: Результат выполнения функции parse_id_and_build.
    :return: Возвращает словарь с ключом Partner ID и значением Build (которое было отправлено в ревью на маркет)
    """
    partner_id_and_review_builds = {i["partner_id"]: i["build"] for i in data_info_partner}
    return partner_id_and_review_builds


def get_package_name(partner_id_and_review_builds) -> dict:
    """
    Функция, которая парсит значение package name из MBA.
    :param partner_id_and_review_builds: Результат выполнения функции get_partner_id_and_review_builds
    :return: Возврщает словарь состоящий из Partner Id и Package name.
    """
    logging.basicConfig(level=logging.ERROR)
    try:
        for partner_id in partner_id_and_review_builds:
            url = "URL + PARTNER_ID" + str(partner_id)
            package_name_info_parse = requests.get(url)
            data_info_package_name = package_name_info_parse.json()
            package_name = data_info_package_name["app_identifiers"]["android"]["package_name"]
            for _ in partner_id_and_review_builds:
                packages_dict[partner_id] = package_name
    except ValueError:
        logging.error(f"Can't get value from app_identifiers for {partner_id}")
    return packages_dict


def get_build_from_gp(packages) -> dict:
    """
    Функция получает аргумент в виде словаря packages_dict. Переходит на Google Play и подставляет в ссылку значение
    словаря, чтобы перейти на страницу приложения. Со страницы приложения берет последнуюю версию приложения
    доступную на маркете.
    :param packages: Результат выполнения функции get_package_name.
    :return: Словарь, где ключ - Partner Id и значение - версия приложения, доступная к скачиванию.
    """
    logging.basicConfig(level=logging.ERROR)
    driver = webdriver.Chrome(ChromeDriverManager().install())
    for package in packages:
        try:
            url = "https://play.google.com/store/apps/details?id="
            driver.get(url + str(packages[package]))
            # Ждем 3 секунды, пока прогрузится маркет.
            time.sleep(3)
            # Открываем окно, с описанием приложения.
            driver.find_element(By.XPATH, "/html/body/c-wiz[2]/div/div/div[1]/div[2]/div/div[1]/c-wiz["
                                          "2]/div/section/header/div/div[2]/button/i").click()
            time.sleep(10)
            # Берем версию приложения оттуда.
            current_build = driver.find_element(By.CLASS_NAME,
                                                'reAt0')
            current_build = current_build.text.split(".")
            current_build = "".join(current_build)
            builds_on_gp[package] = int(current_build)
        except NoSuchElementException:
            logging.error(f'Something wrong with partner = {package}')

    driver.quit()

    return builds_on_gp


def get_compare_builds(partner_id_and_review_builds) -> dict:
    """
    Функция сравнения версий приложений. Берется два словаря:
    1. Словарь тех версий приложений, что были отправлены в ревью
    2. Словарь тех версий приложений, что доступны к скачиванию в Google Play Console.
    Сравниваются значения этих словарей и создается новый словарь с соответствующим значением для каждого ключа.
    :param partner_id_and_review_builds: Результат выполнения функции get_partner_id_and_review_builds. Передается этот
    параметр ровно потому, что если приложение было отправлено в ревью, но оно еще не доступно к скачиванию, то функция
    выпадет в ошибку.
    :return: Возвращает словарь состоящий из ключа - Partner Id и значения, в виде статуса приложения.
    """
    for i in builds_on_gp:
        if builds_on_gp[i] == partner_id_and_review_builds[i]:
            compare_builds[i] = 'Release'
        else:
            compare_builds[i] = 'Review'

    return compare_builds


def set_build_on_mba(build_gp, partner_review_build):
    logging.info("Try to put the value in MBA")
    for partner_id in partner_review_build:
        if partner_review_build[partner_id] == build_gp[partner_id]:
            build = partner_review_build[partner_id]
            logging.info(f'The value in build step = {build}')
            mobile_api = MobileBuildApi()
            mobile_api.build_patch(PlatformType.ANDROID, build, Status.RELEASE_SUPPORTED)
        else:
            logging.info(f'Skip this version')
            pass


if __name__ == '__main__':
    main()
