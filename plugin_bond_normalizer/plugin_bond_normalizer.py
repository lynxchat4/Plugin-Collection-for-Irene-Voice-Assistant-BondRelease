import os
import re
from logging import getLogger
from typing import Optional, Any
from irene.face.abc import FileWritingTTS, TTSResultFile
from irene.utils.metadata import MetadataMapping

name = 'tts_text_normalizer'
version = '0.2.0B'

_logger = getLogger(name)


class _TextNormalizerTTS(FileWritingTTS):
    def __init__(self, wrapped: FileWritingTTS):
        self._wrapped = wrapped
        _logger.debug("Инициализирован нормализатор текста TTS")

    def normalize_text(self, text: str) -> str:
        """
        Основная функция нормализации текста
        """
        _logger.debug(f'Текст до преобразований: {text}')

        # Если в строке только кириллица и пунктуация - оставляем как есть
        if not bool(re.search(r'[^,.?!;:"() ЁА-Яа-яё]', text)):
            return text

        def replace_characters(input_string, replacement_dict):
            """
            Замена символов в строке по словарю подстановки
            """
            translation_table = str.maketrans(replacement_dict)
            return input_string.translate(translation_table)

        # Замена символов текстом
        if bool(re.search(r'["-+\-/<->@{-}№]', text)):
            # Словарь замены символов
            symbol_dict = {
                '!': '!', '"': ' двойная кавычка ', '#': ' решётка ', '$': ' доллар ', '%': ' процент ',
                '&': ' амперсанд ', "'": ' кавычка ', '(': ' левая скобка ', ')': ' правая скобка ',
                '*': ' звёздочка ', '+': ' плюс ', ',': ',', '-': ' минус ', '.': '.', '/': ' косая черта ',
                ':': ':', ';': ';', '<': 'меньше', '=': ' равно ', '>': 'больше', '?': '?', '@': ' эт ',
                '~': ' тильда ', '[': ' левая квадратная скобка ', '\\': ' обратная косая черта ',
                ']': ' правая квадратная скобка ', '^': ' циркумфлекс ', '_': ' нижнее подчеркивание ',
                '`': ' обратная кавычка ', '{': ' левая фигурная скобка ', '|': ' вертикальная черта ',
                '}': ' правая фигурная скобка ',
                '№': ' номер ',
            }

            # Используем все символы из словаря для замены
            symbols_to_change = r"#$%&*+-/<=>@~[\]_`{|}№"
            filtered_symbol_dict = {key: value for key, value in symbol_dict.items() if key in symbols_to_change}
            _logger.debug(f'Словарь замены символов: {filtered_symbol_dict}')

            symbols_to_keep = r",.?!;:() "
            filtered_symbol_dict.update({key: key for key in symbols_to_keep})
            _logger.debug(f'Словарь с сохраняемыми символами: {filtered_symbol_dict}')

            if filtered_symbol_dict:
                text = replace_characters(text, filtered_symbol_dict)
                _logger.debug(f'Текст после замены символов: {text}')

            # Удаляем все остальные символы
            text = re.sub(f'[^{symbols_to_change}{symbols_to_keep}A-Za-zЁА-Яа-яё ]', '', text)
            _logger.debug(f'Текст после удаления символов: {text}')

            text = re.sub(r'[\s]+', ' ', text)  # убрать лишние пробелы

        # Замена чисел словами
        if bool(re.search(r'[0-9]', text)):
            # Простая замена чисел (можно улучшить при необходимости)
            number_replacements = {
                '0': 'ноль ', '1': 'один ', '2': 'два ', '3': 'три ', '4': 'четыре ',
                '5': 'пять ', '6': 'шесть ', '7': 'семь ', '8': 'восемь ', '9': 'девять '
            }
            for num, word in number_replacements.items():
                text = text.replace(num, word)
            _logger.debug(f'Текст после замены чисел: {text}')

        # Замена латиницы на русскую транскрипцию
        if bool(re.search('[a-zA-Z]', text)):
            _logger.debug("Обнаружена латиница, пытаюсь преобразовать")
            
            try:
                import eng_to_ipa as ipa
                
                # Преобразуем в транскрипцию
                ipa_text = ipa.convert(text)
                _logger.debug(f'Текст после преобразования латиницы в транскрипцию: {ipa_text}')

                # Словарь замены транскрипции IPA к русскоязычному фонетическому представлению
                ipa2ru_map = {
                    "p": "п", "b": "б", "t": "т", "d": "д", "k": "к", "g": "г", "m": "м", "n": "н", "ŋ": "нг", "ʧ": "ч",
                    "ʤ": "дж", "f": "ф", "v": "в", "θ": "т", "ð": "з", "s": "с", "z": "з", "ʃ": "ш", "ʒ": "ж", "h": "х",
                    "w": "в", "j": "й", "r": "р", "l": "л",
                    "i": "и", "ɪ": "и", "e": "э", "ɛ": "э", "æ": "э", "ʌ": "а", "ə": "е", "u": "у", "ʊ": "у", "oʊ": "оу",
                    "ɔ": "о", "ɑ": "а", "aɪ": "ай", "aʊ": "ау", "ɔɪ": "ой", "ɛr": "ё", "ər": "ё", "ɚ": "а", "ju": "ю",
                    "əv": "ов", "o": "о",
                    "ˈ": "", "ˌ": "", "*": "",
                }

                def ipa2ru_at_pos(ipa_text: str, pos: int) -> tuple[str, int]:
                    ch = ipa_text[pos]
                    ch2 = ipa_text[pos: pos + 2]
                    if ch2 in ipa2ru_map:
                        return ipa2ru_map[ch2], pos + 2
                    if ch in ipa2ru_map:
                        return ipa2ru_map[ch], pos + 1
                    if ord(ch) < 128:
                        return ch, pos + 1
                    return f"{ch}", pos + 1

                def ipa2ru(ipa_text: str) -> str:
                    result = ""
                    pos = 0
                    while pos < len(ipa_text):
                        ru_ch, pos = ipa2ru_at_pos(ipa_text, pos)
                        result += ru_ch
                    return result

                text = ipa2ru(ipa_text)
                _logger.info(f'Текст после преобразования латиницы: {text}')

            except ImportError:
                _logger.warning("Библиотека eng_to_ipa не установлена. Латиница не будет преобразована.")
                _logger.warning("Установите: pip install eng_to_ipa")
            except Exception as e:
                _logger.error(f"Ошибка при преобразовании латиницы: {e}")
                _logger.warning("Латиница не будет преобразована")

        return text

    def say_to_file(self, text: str, file_base_path: Optional[str] = None, **kwargs) -> TTSResultFile:
        _logger.debug(f"Получен текст для озвучки: '{text}'")
        
        # Нормализуем текст
        normalized_text = self.normalize_text(text)
        _logger.debug(f"Нормализованный текст: '{normalized_text}'")
        
        # Передаем нормализованный текст дальше в TTS
        _logger.debug("Передаю текст в следующий TTS")
        result = self._wrapped.say_to_file(normalized_text, file_base_path, **kwargs)
        _logger.debug("Озвучка завершена успешно")
        
        return result

    @property
    def meta(self) -> MetadataMapping:
        return self._wrapped.meta

    def get_name(self) -> str:
        return self._wrapped.get_name()

    def get_settings_hash(self) -> str:
        return self._wrapped.get_settings_hash()


def create_file_tts(nxt, prev: Optional[FileWritingTTS], config: dict[str, Any], *args, **kwargs):
    _logger.debug("Функция create_file_tts вызвана")
    
    if (tts := nxt(prev, config, *args, **kwargs)) is None:
        _logger.warning("Следующий TTS вернул None, возвращаю None")
        return None

    _logger.debug(f"Создаю обёртку для TTS: {tts.get_name()}")
    return _TextNormalizerTTS(tts)


def init(*args, **kwargs):
    _logger.info("Плагин tts_text_normalizer инициализирован")


def run(*args, **kwargs):
    _logger.debug("Функция run вызвана")