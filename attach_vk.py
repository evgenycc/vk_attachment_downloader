"""
Скрипт для скачивания вложений из групп ВК. Для работы требует установки
следующих библиотек: pip install vk-api colorama requests simple-term-menu
"""

import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from colorama import Fore
from colorama import init
from simple_term_menu import TerminalMenu
from vk_api import VkApi
from vk_api.exceptions import ApiError

from set import token

init()

headers = {
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 "
                  "YaBrowser/22.11.3.838 Yowser/2.5 Safari/537.36",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,"
              "application/signed-exchange;v=b3;q=0.9"
}


class VKAttach:
    """
    Класс для поиска и скачивания вложений из групп ВК.
    """
    def __init__(self, group_url: str, ext: list):
        """
        Инициализация класса.
        :param group_url: Ссылка на группу или экранное имя.
        :param ext: Список с расширениями для фильтрации вложений.
        """
        self.session = VkApi(token=token)
        self.group_url = group_url
        self.ext = ext

        self.group_name = self.parse_group_name()
        self.group_id, self.screen_name = self.get_group_info()
        self.post_count = self.get_post_count()
        self.path = Path.cwd() / 'channels' / self.screen_name
        self.files = set()
        self.files_url = set()

    def parse_group_name(self) -> str:
        """
        Парсит имя группы из ссылки. Если указано имя группы без ссылки,
        забирает его.
        :return: Возвращает имя группы.
        """
        if self.group_url.endswith("/"):
            self.group_name = self.group_url[0:-1]
        if self.group_url.startswith("http"):
            self.group_name = self.group_url.split("/")[-1]
        else:
            self.group_name = self.group_url
        return self.group_name

    def get_group_info(self) -> tuple:
        """
        Получение базовой информации о группе, требующейся для работы скрипта.
        Забирается ID группы, а также экранное имя, то имя, что отображается в ссылке.
        :return: Возвращает ID группы и экранное имя.
        """
        try:
            group = self.session.get_api().groups.getById(group_id=self.group_name, access_token=token, v=5.131)
            return group[0]['id'], group[0]['screen_name']
        except ApiError:
            print('Некорректное имя группы')
            exit(0)

    def get_post_count(self) -> int:
        """
        Получает количество постов в группе.
        :return: Возвращает количество постов.
        """
        try:
            return self.session.get_api().wall.get(owner_id=f'-{self.group_id}',
                                                   access_token=token, v=5.131, offset=0, count=1)['count']
        except ApiError:
            print("Доступ запрещен. Закрытая группа")
            sys.exit(0)

    def scan_dir(self):
        """
        Получает файлы из директории, куда скачиваются вложения.
        Заполняет глобальный словарь определенный при инициализации класса.
        """
        if self.path.exists():
            for file in self.path.iterdir():
                self.files.add(Path(file).name)

    def get_file(self, url: str, title: str):
        """
        Скачивает файлы из вложений.
        :param url: Ссылка на файл из вложения.
        :param title: Название файла.
        :return: Возвращает None в случае исключения.
        """
        try:
            res = requests.get(url=url, headers=headers)
            if 200 <= res.status_code <= 299:
                with open(self.path / title, 'wb') as f:
                    f.write(res.content)
                print(f'Загрузка: {title}')
        except requests.exceptions.ConnectionError:
            return

    def print_info(self):
        """
        Вывод информации в терминал о группе, количестве публикаций, а также
        количестве файлов в директории куда загружаются вложения.
        """
        subprocess.call("clear", shell=True)
        print(f'\n{Fore.CYAN}Информация о группе\n{"-" * 25}')
        print(f'{Fore.GREEN}ID: {Fore.RESET}-{self.group_id} | {Fore.GREEN}Screen Name: '
              f'{Fore.RESET}{self.screen_name}')
        print(f"{Fore.YELLOW}Количество публикаций: {Fore.RESET}{self.post_count}")
        print(f'{Fore.GREEN}Файлы в директории: {Fore.RESET}{len(self.files)}\n')

        if self.files_url:
            for num, uri in enumerate(self.files_url):
                ur = uri.split("\n")[0]
                print(f'{str(num+1).ljust(3)}| Найдено: {ur}')

    def get_posts(self):
        """
        Получение всех постов группы, итерация по постам, получение информации о вложениях.
        Заполнение словаря в случае найденного вложения, в соответсвии с расширениями
        из глобального словаря. Выполняет подсчет объектов в словаре, куда складываются найденные
        названия файлов и ссылки. В случае, если количество объектов больше или равно 10,
        запускает скачивание файлов вложений.
        :return: Возвращает None в случае исключения.
        """
        time_start = time.monotonic()
        self.scan_dir()
        self.print_info()

        for offset in range(0, self.post_count, 100):
            self.scan_dir()
            posts = self.session.get_api().wall.get(owner_id=f'-{self.group_id}', access_token=token,
                                                    v=5.131, offset=offset, count=100)
            for post in posts['items']:
                try:
                    if post.get('attachments') is not None:
                        for i in range(0, len(post.get('attachments'))):
                            try:
                                if post.get('attachments')[i].get('doc').get('ext') in self.ext:
                                    title = post.get('attachments')[i].get('doc').get('title')
                                    ex = post.get('attachments')[i].get('doc').get('ext')
                                    try:
                                        title = f'{Path(title).name.split(Path(title).suffix)[0].strip()}.{ex}'
                                    except ValueError:
                                        title = f'{title.strip()}.{ex}'
                                    url = post.get('attachments')[i].get('doc').get('url')

                                    if len(self.files_url) >= 10:
                                        self.print_info()
                                        self.path.parent.mkdir(exist_ok=True)
                                        self.path.mkdir(exist_ok=True)
                                        print("")
                                        with ThreadPoolExecutor(max_workers=10) as executor:
                                            for file in self.files_url:
                                                tt = file.split("\n")[0].strip()
                                                url = file.split("\n")[1].strip()
                                                self.files.add(tt)
                                                executor.submit(self.get_file, url=url, title=tt)
                                            self.files_url.clear()
                                        print("")

                                    if title not in self.files:
                                        self.files_url.add(f'{title}\n{url}')
                                    else:
                                        print(f'{Fore.YELLOW}Существует: {Fore.RESET}"{title}"')
                            except AttributeError:
                                continue
                        continue
                except IndexError:
                    return

        if len(self.files_url) < 10:
            self.print_info()
            self.path.parent.mkdir(exist_ok=True)
            self.path.mkdir(exist_ok=True)
            print("")
            with ThreadPoolExecutor(max_workers=10) as executor:
                for file in self.files_url:
                    tt = file.split("\n")[0].strip()
                    url = file.split("\n")[1].strip()
                    self.files.add(tt)
                    executor.submit(self.get_file, url=url, title=tt)
            self.files_url.clear()
        self.print_info()
        print(f'{Fore.GREEN}Затрачено времени {Fore.RESET}| '
              f'{(int(time.monotonic() - time_start) // 3600) % 24:d} ч. '
              f'{(int(time.monotonic() - time_start) // 60) % 60:02d} м. '
              f'{int(time.monotonic() - time_start) % 60:02d} с.\n')


def menu(link: str):
    """
    Создание меню для навигации с помощью клавиш. Создание экземпляра класса
    в соответствии с выбранными параметрами. Запуск получения постов группы и
    скачивания вложений, если таковые имеются.
    :param link: Ссылка на группу или экранное имя.
    """
    try:
        ext = []
        img = ["psd", "jpg", "jpeg", "png", "gif", "tiff", "ico", "svg", "webp", "bmp"]
        doc = ["pdf", "odt", "ods", "doc", "docx", "xls", "xlsx", "fb2", "mobi", "epub", "djvu", "djv", "zip", "rar",
               "tar"]
        pls = ["m3u", "m3u8"]

        subprocess.call("clear", shell=True)
        print(f'{Fore.GREEN}Выбор формата вложений для загрузки\n{"-" * 25}\n')
        opt = ["1.Изображения", "2.Документы", "3.Плейлисты", "4.Все форматы", "5.Выход"]
        ch = TerminalMenu(opt).show()
        if opt[ch] == "1.Изображения":
            attach = VKAttach(link, img)
            attach.get_posts()
        elif opt[ch] == "2.Документы":
            attach = VKAttach(link, doc)
            attach.get_posts()
        elif opt[ch] == "3.Плейлисты":
            attach = VKAttach(link, pls)
            attach.get_posts()
        elif opt[ch] == "4.Все форматы":
            ext.extend(img)
            ext.extend(doc)
            ext.extend(pls)
            attach = VKAttach(link, ext)
            attach.get_posts()
        elif opt[ch] == "5.Выход":
            raise KeyboardInterrupt
    except (KeyboardInterrupt, TypeError):
        subprocess.call("clear", shell=True)
        print(f"\n{Fore.GREEN}Good By!\n")
        sys.exit(0)


def main():
    """
    Запрос у пользователя ссылки на группу.
    Запуск создания меню выбора дальнейших действий.
    """
    link = input(Fore.RESET + "\nВведите ссылку на группу: ")
    menu(link)


if __name__ == "__main__":
    main()
