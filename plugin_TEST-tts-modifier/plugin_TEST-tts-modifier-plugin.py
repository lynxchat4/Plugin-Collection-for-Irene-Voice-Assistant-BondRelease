import os
from logging import getLogger
from typing import Optional, Any
from irene.face.abc import FileWritingTTS, TTSResultFile
from irene.utils.metadata import MetadataMapping

name = 'tts_text_modifier'
version = '0.1.1'

_logger = getLogger(name)


class _TextModifierTTS(FileWritingTTS):
    def __init__(self, wrapped: FileWritingTTS):
        self._wrapped = wrapped
        _logger.debug("Инициализирован модификатор текста TTS")

    def say_to_file(self, text: str, file_base_path: Optional[str] = None, **kwargs) -> TTSResultFile:
        # Логируем входящий текст
        _logger.debug(f"Получен текст для озвучки: '{text}'")
        _logger.debug(f"Дополнительные параметры: {kwargs}")
        
        # Добавляем слово "тест" к входящему тексту
        modified_text = f"{text} тест"
        _logger.debug(f"Модифицированный текст: '{modified_text}'")
        
        # Передаем модифицированный текст дальше в TTS
        _logger.debug("Передаю текст в следующий TTS")
        result = self._wrapped.say_to_file(modified_text, file_base_path, **kwargs)
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
    _logger.debug(f"Предыдущий TTS: {prev}")
    _logger.debug(f"Конфиг: {config}")
    
    if (tts := nxt(prev, config, *args, **kwargs)) is None:
        _logger.warning("Следующий TTS вернул None, возвращаю None")
        return None

    _logger.debug(f"Создаю обёртку для TTS: {tts.get_name()}")
    return _TextModifierTTS(tts)


def init(*args, **kwargs):
    _logger.info("Плагин tts_text_modifier инициализирован")
    _logger.debug(f"Аргументы init: args={args}, kwargs={kwargs}")


def run(*args, **kwargs):
    _logger.debug("Функция run вызвана")