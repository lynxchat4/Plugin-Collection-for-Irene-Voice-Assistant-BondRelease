import os
import random
import logging
import re
from typing import Any, TypedDict
import requests
from vacore import VACore

modname = os.path.basename(__file__)[:-3]  # calculating modname
logger = logging.getLogger(modname)

def start(core: VACore):
    manifest = {
        'name': 'Плагин для Home Assistant',
        'version': '0.2',
        'require_online': True,

        'default_options': {
            'hassio_url': 'http://hassio.lan:8123/',
            'hassio_key': '',  # получить в /profile, 'Долгосрочные токены доступа'
            'default_reply': ['Хорошо', 'Выполняю', 'Будет сделано'],
            # ответить если в описании скрипта не указан ответ в формате 'ttsreply(текст)'
            'totem': '🎤',
            # Unicode символ который будет у доступных Ирине сенсоров, выключателей и скриптов.
        },

        'commands': {
            'включи': hassio_call('switch_on'),
            'выключи': hassio_call('switch_off'),
            'хочу|сделай|я буду': hassio_call('script'),
            'перезагрузи устройства|загрузи устройства|перезагрузи хоум|загрузи хоум': hassio_call('reload'),
            'какая': hassio_call('sensor'),
        }
    }

    return manifest

def start_with_options(core: VACore, manifest: dict):
    core.hassio = _HomeAssistant(core.plugin_options(modname), core)
    core.hassio.reload()

def hassio_call(method):
    def decorator(core: VACore, phrase: str):
        # в этот момент объект уже должен быть инициализирован
        if not hasattr(_HomeAssistant, 'instance'):
            raise RuntimeError('HomeAssistant not initialized')
        ha = _HomeAssistant.instance
        if not hasattr(ha, f'call_{method}'):
            raise NotImplementedError(f'{method} call not implemented')
        return getattr(ha, f'call_{method}')(phrase)

    return decorator

class _HomeAssistant:
    entities: TypedDict('EntitiesNameMap', {'switch': dict[str, str], 'sensor': dict[str, str]})
    scripts: dict[str, TypedDict('ScriptDomain', {'name': str, 'description': str, })]

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, 'instance'):
            cls.instance = super(_HomeAssistant, cls).__new__(cls)
        return cls.instance

    def __init__(self, options: dict[str, Any], core: VACore):
        if not options['hassio_url']:
            core.play_voice_assistant_speech('Не задан урл хоум ассистанта, не могу запуститься')
            logger.error('Hassio url not set')
            raise AttributeError('Hassio url not set')
        if not options['hassio_key']:
            core.play_voice_assistant_speech('Не задан ключ апи хоум ассистанта, не могу запуститься')
            logger.error('Hassio api key not set')
            raise AttributeError('Hassio api key not set')
        self.url = options['hassio_url'].strip().rstrip('/')
        self.api_key = options['hassio_key'].strip()
        self.default_replies = options['default_reply']
        self.totem = options['totem']
        self.va_core = core

        # используется библиотека pymorphy2 она нормализует слова
        try:
            import pymorphy2
            self.morph = pymorphy2.MorphAnalyzer()
        except ImportError:
            self.morph = None

    def request(self, path: str, method: str = 'GET', **kwargs):
        if not kwargs.get('headers'):
            kwargs['headers'] = {}
        kwargs['headers'].update({'Authorization': 'Bearer ' + self.api_key})
        try:
            res = requests.request(method, f'{self.url}/api/{path.lstrip("/")}', **kwargs)
            res.raise_for_status()
            return res.json()
        except Exception as e:
            self.say_if_va('При запросе хоум ассистанта произошла ошибка')
            logger.exception(f'Request {path} exception: {type(e)}')
            import traceback
            traceback.print_exc()

    def call_script(self, phrase):
        no_script = True
        phrase += self.totem
        phrase = self.prepare_phrase(phrase)
        for script in self.scripts:
            if str(self.scripts[script]['name']) == phrase:  # ищем скрипт с подходящим именем
                self.request(f'services/script/{script}', 'POST')
                script_desc = str(
                    self.scripts[script]['description'])  # бонус: ищем что ответить пользователю из описания скрипта
                if 'ttsreply(' in script_desc and ')' in script_desc.split('ttsreply(')[1]:  # обходимся без re :^)
                    self.say_if_va(script_desc.split('ttsreply(')[1].split(')')[0])
                else:  # если в описании ответа нет, выбираем случайный ответ по умолчанию
                    self.default_reply()
                no_script = False
                break
        if no_script:
            self.say_if_va('Нет такого сценария')

    def call_switch_on(self, phrase):
        phrase += self.totem
        phrase = self.prepare_phrase(phrase)
        if phrase not in self.entities['switch']:
            self.say_if_va('Нет такого устройства')
        if self.request('services/switch/turn_on', 'POST', json={
            'entity_id': self.entities['switch'][phrase]
        }) is not None:
            self.default_reply()

    def call_switch_off(self, phrase):
        phrase += self.totem
        phrase = self.prepare_phrase(phrase)
        if phrase not in self.entities['switch']:
            self.say_if_va('Нет такого устройства')
        elif self.request('services/switch/turn_off', 'POST', json={
            'entity_id': self.entities['switch'][phrase]
        }) is not None:
            self.default_reply()

    def call_sensor(self, phrase):
        phrase += self.totem
        phrase = self.prepare_phrase(phrase)
        if phrase not in self.entities['sensor']:
            self.say_if_va('Нет такого устройства')
            print("Нет такого устройства")
            return None
        state = self.request(f'states/{self.entities["sensor"][phrase]}')
        if not state:
            self.say_if_va('Не удалось получить статус устройства')
        state_type = state.get('attributes', {}).get('device_class')
        val = int(float(state["state"]))
        if state_type in ('temperature', 'humidity'):
            sensor_name = state.get("attributes").get("friendly_name", phrase)
            sensor_name = re.sub(r'[^а-яА-ЯёЁ\s]', '', sensor_name)
            self.say_if_va(f'{sensor_name} сейчас {self.num2text(val)}'
                           f' {self.unit_of_measurement(state.get("attributes", {}).get("unit_of_measurement"), val)}')
        elif state_type == 'battery':
            sensor_name = state.get("attributes").get("friendly_name", phrase)
            sensor_name = re.sub(r'[^а-яА-ЯёЁ\s]', '', sensor_name)
            self.say_if_va(
                f'заряд {sensor_name} сейчас {self.num2text(val)}'
                f' {self.unit_of_measurement(state.get("attributes", {}).get("unit_of_measurement"), val)}')
        else:
            self.say_if_va('Статус данного устройства не поддерживается')

    def call_reload(self, phrase):
        self.reload()
        not_found = False
        for entity, name in {'switch': 'Выключатели', 'sensor': 'Сенсоры'}.items():
            if not self.entities[entity]:
                not_found = True
                self.say_if_va(f'{name} не найдены')
        if not self.scripts:
            not_found = True
            self.say_if_va('Скрипты не найдены')
        if not not_found:
            self.say_if_va('Устройства успешно загр+ужены')

    def reload(self):
        # загружаем скрипты
        services = self.request('services')
        for service in services:  # ищем скрипты среди списка доступных сервисов
            if service['domain'] == 'script':
                self.scripts = service['services']

                # нормальзуем название скриптов
                for script in self.scripts:
                    self.scripts[script]['name'] = self.prepare_phrase(self.scripts[script]['name'])
                print('')
                print('---------Список загруженных скриптов---------')
                for script in self.scripts:
                    if self.scripts[script]['name']:
                        print(self.scripts[script]['name'])
                break
        self.entities = {
            'switch': {},
            'sensor': {},
        }
        # загружаем states
        states = self.request('states')
        for state in states:
            for entity_type in ['switch', 'sensor']:
                if state['entity_id'].startswith(f'{entity_type}.'):
                    if not state.get('attributes', {}).get('friendly_name'):
                        # устройства без имени не добавляем
                        continue
                    clean_name = self.prepare_phrase(state['attributes']['friendly_name'])
                    if not clean_name:
                        # устройства без имени после обработки не добавляем
                        continue
                    if self.entities[entity_type].get(clean_name):
                        self.say_if_va(f'Предупреждаю, что найдено два устройства с именем '
                                       f'{state["attributes"]["friendly_name"]} '
                                       f'будет работать только первый')
                        logger.warning(f'Multiple friendly name {state["attributes"]["friendly_name"]}')
                    self.entities[entity_type][clean_name] = state['entity_id']
                    break
        print('')
        print('---------Список загруженных датчиков---------')
        if self.entities["sensor"]:
            for name, id in self.entities["sensor"].items():
                print(f"{name}")
        print('')
        print('------Список загруженных выключателей--------')
        if self.entities["switch"]:
            for name, id in self.entities["switch"].items():
                print(f"{name}")
        print('')
        print('---------------------------------------------')

    def default_reply(self):
        self.say_if_va(self.default_replies[random.randint(0, len(self.default_replies) - 1)])

    def say_if_va(self, phrase):
        if self.va_core.va:
            self.va_core.play_voice_assistant_speech(phrase)

    def prepare_phrase(self, phrase):
        # Проверяем наличие символа "totem"
        if self.totem not in phrase:
            phrase = ""
        else:
            #изменить, если захотите включить  mystem
            #if self.mystem:
            if self.morph:
                phrase = re.sub(r'[^а-яА-ЯёЁ\s]', '', phrase)
                phrase = ' '.join(
                    self.morph.parse(word.lower())[0].normal_form for word in re.split(r'\W+', phrase) if word.strip())
                # изменить, если захотите включить  mystem
                #phrase = ' '.join(lem.strip().lower() for lem in self.mystem.lemmatize(phrase) if lem.strip())
                return phrase
            else:
                phrase = re.sub(r'[^а-яА-ЯёЁ\s]', '', phrase)
                phrase = phrase.strip().lower()
                return phrase

    @staticmethod
    def unit_of_measurement(key, value):
        forms = {
            '°C': ['градус', 'градуса', 'градусов'],
            '%': ['процент', 'процента', 'процентов'],
            '°F': ['фаренгейт', 'фаренгейта', 'фаренгейтов'],

        }.get(key)
        if not forms:
            return key

        # Логика выбора формы в зависимости от числа
        remainder10 = value % 10
        remainder100 = value % 100

        if 11 <= remainder100 <= 19:
            return forms[2]
        elif remainder10 == 1:
            return forms[0]
        elif 2 <= remainder10 <= 4:
            return forms[1]
        else:
            return forms[2]

    @staticmethod
    def num2text(num, main_units=((u'', u'', u''), 'm')):
        """
        author Sergey Prokhorov (https://github.com/seriyps/ru_number_to_text)
        """
        units = (
            u'ноль',
            (u'один', u'одна'),
            (u'два', u'две'),
            u'три', u'четыре', u'пять',
            u'шесть', u'семь', u'восемь', u'девять'
        )

        teens = (
            u'десять', u'одиннадцать',
            u'двенадцать', u'тринадцать',
            u'четырнадцать', u'пятнадцать',
            u'шестнадцать', u'семнадцать',
            u'восемнадцать', u'девятнадцать'
        )

        tens = (
            teens,
            u'двадцать', u'тридцать',
            u'сорок', u'пятьдесят',
            u'шестьдесят', u'семьдесят',
            u'восемьдесят', u'девяносто'
        )

        hundreds = (
            u'сто', u'двести',
            u'триста', u'четыреста',
            u'пятьсот', u'шестьсот',
            u'семьсот', u'восемьсот',
            u'девятьсот'
        )

        orders = (  # plural forms and gender
            ((u'тысяча', u'тысячи', u'тысяч'), 'f'),
            ((u'миллион', u'миллиона', u'миллионов'), 'm'),
            ((u'миллиард', u'миллиарда', u'миллиардов'), 'm'),
        )

        minus = u'минус'

        def thousand(rest, sex):
            """Converts numbers from 19 to 999"""
            prev = 0
            plural = 2
            name = []
            use_teens = rest % 100 >= 10 and rest % 100 <= 19
            if not use_teens:
                data = ((units, 10), (tens, 100), (hundreds, 1000))
            else:
                data = ((teens, 10), (hundreds, 1000))
            for names, x in data:
                cur = int(((rest - prev) % x) * 10 / x)
                prev = rest % x
                if x == 10 and use_teens:
                    plural = 2
                    name.append(teens[cur])
                elif cur == 0:
                    continue
                elif x == 10:
                    name_ = names[cur]
                    if isinstance(name_, tuple):
                        name_ = name_[0 if sex == 'm' else 1]
                    name.append(name_)
                    if cur >= 2 and cur <= 4:
                        plural = 1
                    elif cur == 1:
                        plural = 0
                    else:
                        plural = 2
                else:
                    name.append(names[cur - 1])
            return plural, name

        _orders = (main_units,) + orders
        if num == 0:
            return ' '.join((units[0], _orders[0][0][2])).strip()  # ноль

        rest = abs(num)
        ord = 0
        name = []
        while rest > 0:
            plural, nme = thousand(rest % 1000, _orders[ord][1])
            if nme or ord == 0:
                name.append(_orders[ord][0][plural])
            name += nme
            rest = int(rest / 1000)
            ord += 1
        if num < 0:
            name.append(minus)
        name.reverse()
        return ' '.join(name).strip()