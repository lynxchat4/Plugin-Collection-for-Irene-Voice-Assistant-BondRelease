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
        'version': '0.3',
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
            'включи|включить|включил|включен': hassio_call('switch_on'),
            'выключи|выключить|выключил|выключен': hassio_call('switch_off'),
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
    entities: TypedDict('EntitiesNameMap', {'switch': dict[str, str], 'light': dict[str, str], 'sensor': dict[str, str]})
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

        # используется библиотека pymorphy3 она нормализует слова
        try:
            import pymorphy3
            self.morph = pymorphy3.MorphAnalyzer()
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

    def get_full_name(self, phrase, structure):
        index = -1
        full_name = ""

        for item in structure:
            name_item = str(item)
            parts_name = name_item.split("|")
            if ('|' not in name_item and name_item == phrase ) or ('|' in name_item and phrase in parts_name):
                full_name = name_item
                if '|' in name_item:
                    index = parts_name.index(phrase)
                break

        return full_name, index

    # Поиск скрипта содержащего ключевую фразу 'включи|включить|...' либо 'выключи|выключить|...'
    def get_script(self, phrase):
        for script in self.scripts:
            name_script = str(self.scripts[script].get('name') or self.scripts[script].get('alias') or '' )
            parts_name_script = name_script.split('|')

            if phrase in parts_name_script:
                return script

        return None

    def call_script(self, phrase):
        no_script = True
        phrase += self.totem
        phrase = self.prepare_phrase(phrase)
        for script in self.scripts:
            # Добавлена поддержка alias для скриптов
            name_script = str(self.scripts[script].get('name') or self.scripts[script].get('alias') or '')
            parts_name_script = name_script.split("|")
            if ('|' not in name_script and name_script == phrase ) or ('|' in name_script and phrase in parts_name_script):
                self.request(f'services/script/{script}', 'POST')
                script_desc = str(
                    self.scripts[script]['description'])
                if 'ttsreply(' in script_desc and ')' in script_desc.split('ttsreply(')[1]:
                    self.say_if_va(script_desc.split('ttsreply(')[1].split(')')[0])
                else:
                    self.default_reply()
                no_script = False
                break
        if no_script:
            self.say_if_va('Нет такого сценария')
            print(f"Нет такого сценария >{phrase}< {self.scripts}")

    def call_switch_on(self, phrase):
        phrase += self.totem
        phrase = self.prepare_phrase(phrase)

        # Сначала ищем устройство
        full_name_switch, _ = self.get_full_name(phrase, self.entities['switch'])
        full_name_light, _ = self.get_full_name(phrase, self.entities['light'])

        if full_name_switch:
            if self.request('services/switch/turn_on', 'POST', json={
                'entity_id': self.entities['switch'][full_name_switch]
            }) is not None:
                self.default_reply()
            return

        if full_name_light:
            if self.request('services/light/turn_on', 'POST', json={
                'entity_id': self.entities['light'][full_name_light]
            }) is not None:
                self.default_reply()
            return

        # Устройство не найдено.
        # Ищем скрипт с полной командой.
        script_phrase = self.prepare_phrase(f'включи {phrase}{self.totem}')

        script = self.get_script(script_phrase)

        if script:
            self.request(f'services/script/{script}', 'POST')

            script_desc = str(
                self.scripts[script].get('description', '')
            )

            if 'ttsreply(' in script_desc and ')' in script_desc.split('ttsreply(')[1]:
                self.say_if_va(script_desc.split('ttsreply(')[1].split(')')[0])
            else:
                self.default_reply()

            return

        self.say_if_va('Нет такого устройства или сценария')
        print(
            f'Не найдено устройство или сценарий: '
            f'устройство >{phrase}<, скрипт >{script_phrase}<'
        )

    def call_switch_off(self, phrase):
        phrase += self.totem
        phrase = self.prepare_phrase(phrase)

        # Сначала ищем устройство
        full_name_switch, _ = self.get_full_name(phrase, self.entities['switch'])
        full_name_light, _ = self.get_full_name(phrase, self.entities['light'])

        if full_name_switch:
            if self.request('services/switch/turn_off', 'POST', json={
                'entity_id': self.entities['switch'][full_name_switch]
            }) is not None:
                self.default_reply()
            return

        if full_name_light:
            if self.request('services/light/turn_off', 'POST', json={
                'entity_id': self.entities['light'][full_name_light]
            }) is not None:
                self.default_reply()
            return

        # Устройство не найдено.
        # Ищем скрипт с полной командой.
        script_phrase = self.prepare_phrase(f'выключи {phrase}{self.totem}')

        script = self.get_script(script_phrase)

        if script:
            self.request(f'services/script/{script}', 'POST')

            script_desc = str(self.scripts[script].get('description', ''))

            if 'ttsreply(' in script_desc and ')' in script_desc.split('ttsreply(')[1]:
                self.say_if_va(script_desc.split('ttsreply(')[1].split(')')[0])
            else:
                self.default_reply()

            return

        self.say_if_va('Нет такого устройства или сценария')
        print(
            f'Не найдено устройство или сценарий: '
            f'устройство >{phrase}<, скрипт >{script_phrase}<'
        )

    def call_sensor(self, phrase):
        phrase += self.totem
        phrase = self.prepare_phrase(phrase)
        full_name_sensor, index_phrase = self.get_full_name(phrase, self.entities['sensor'])
        if full_name_sensor == "":
            self.say_if_va('Нет такого сенсора')
            print(f"Нет такого сенсора >{phrase}< среди {self.entities['sensor']}")
            return None
        state = self.request(f'states/{self.entities["sensor"][full_name_sensor]}')
        if not state:
            self.say_if_va('Не удалось получить статус устройства')
        state_type = state.get('attributes', {}).get('device_class')
        val = int(float(state["state"]))
        if state_type in ('temperature', 'humidity'):
            sensor_name = state.get("attributes").get("friendly_name", phrase)
            sensor_name = re.sub(r'[^а-яА-ЯёЁ\s\|]', '', sensor_name)
            if '|' in sensor_name:
                parts = sensor_name.split("|")
                sensor_name = parts[index_phrase]
            self.say_if_va(f'{sensor_name} сейчас {self.num2text(val)}'
                           f' {self.unit_of_measurement(state.get("attributes", {}).get("unit_of_measurement"), val)}')
        elif state_type == 'battery':
            sensor_name = state.get("attributes").get("friendly_name", phrase)
            sensor_name = re.sub(r'[^а-яА-ЯёЁ\s\|]', '', sensor_name)
            if '|' in sensor_name:
                parts = sensor_name.split("|")
                sensor_name = parts[index_phrase]
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
                    if 'name' in self.scripts[script]:
                        self.scripts[script]['name'] = self.prepare_phrase(self.scripts[script]['name'])
                print('')
                print('---------Список загруженных скриптов---------')
                for script in self.scripts:
                    if 'name' in self.scripts[script] and self.scripts[script]['name']:
                        print(self.scripts[script]['name'])
                break
        self.entities = {
            'switch': {},
            'light': {},
            'sensor': {},
        }
        # загружаем states
        states = self.request('states')
        for state in states:
            for entity_type in ['switch', 'light', 'sensor']:
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
        print('------Список загруженных светильников--------')
        if self.entities["light"]:
            for name, id in self.entities["light"].items():
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
                phrase = re.sub(r'[^а-яА-ЯёЁ\s\|]', '', phrase)
                if '|' not in phrase:
                    phrase = ' '.join(
                        self.morph.parse(word.lower())[0].normal_form for word in re.split(r'\W+', phrase) if word.strip())
                    # изменить, если захотите включить  mystem
                    #phrase = ' '.join(lem.strip().lower() for lem in self.mystem.lemmatize(phrase) if lem.strip())
                else:
                    # если объект содержит подсписок, то нормализуем по частям
                    parts = phrase.split('|')
                    processed_parts = []
                    for part in parts:
                        processed_part = ' '.join(self.morph.parse(word.lower())[0].normal_form for word in re.split(r'\W+', part) if word.strip())
                        processed_parts.append(processed_part)
                    phrase = '|'.join(processed_parts)
                return phrase
            else:
                phrase = re.sub(r'[^а-яА-ЯёЁ\s\|]', '', phrase)
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
