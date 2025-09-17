# Список дел
# author: ntirs 

import os
import logging


from vacore import VACore


modname = os.path.basename(__file__)[:-3]  # calculating modname
logger = logging.getLogger(__name__) 


# функция на старте
def start(core:VACore):
    manifest = { # возвращаем настройки плагина - словарь
        "name": "Список дел", # имя
        "version": "1.0", # версия
        "require_online": False, # требует ли онлайн?

        "description": "Плагин список дел\n"
                       "Голосовая команда: дела|список дел",

        "options_label": {
            "todo_file_path": 'путь к файлу списка дел',
        },

        "default_options": {
            "todo_file_path": "", # 
        },


        "commands": { # набор скиллов. Фразы скилла разделены | . Если найдены - вызывается функция
            "дела|список дел|что в списке": read_todo_list,
            "запиши|новое дело|добавь дело": new_todo,
            "удали дела|новый список": clear_todo_list,

        }
    }
    return manifest

def start_with_options(core:VACore, manifest:dict):
    pass

def get_todo_file_path(core: VACore):
    options = core.plugin_options(modname)  # Получаем настройки
    return options["todo_file_path"]

def read_todo_list(core:VACore, phrase: str):
    
    TODO_FILE_PATH = get_todo_file_path(core)  

    if not os.path.exists(TODO_FILE_PATH):
        message = "Файл со списком дел не найден."
        core.play_voice_assistant_speech(message)
        logger.info(f"{message}")
        return

    try:
        with open(TODO_FILE_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        if not lines:
            message = "Список дел пуст."
            core.play_voice_assistant_speech(message)
            logger.info(f"{message}")
            return

        message = "Ваш список дел:"
        logger.info(f"{message}")
        core.play_voice_assistant_speech(message)

        for i, line in enumerate(lines):
            task = line.strip()
            if task:  # Пропускаем пустые строки
                task_message = f"Дело {i + 1}: {task}"
                logger.info(f"{task_message}")
                core.play_voice_assistant_speech(task_message)

    except Exception as e:
        error_message = f"Произошла ошибка при чтении списка дел: {e}"
        core.play_voice_assistant_speech(error_message)
        logger.error(f"{error_message}")

def new_todo(core:VACore, phrase: str): # в phrase находится остаток фразы после названия скилла,
                                              # если юзер сказал больше

    core.play_voice_assistant_speech("Что надо записать")
    core.context_set(add_todo_item)

def add_todo_item(core:VACore, phrase: str):

    TODO_FILE_PATH = get_todo_file_path(core)  

    item = phrase   
    if not item.strip():
        message = "Вы не указали, что нужно добавить в список дел."
        core.play_voice_assistant_speech(message)
        logger.info(f"{message}")
        return

    try:
       
        with open(TODO_FILE_PATH, 'a', encoding='utf-8') as f:
            f.write(item.strip() + '\n')

        message = f"Добавлено в список дел: {item.strip()}"
        core.play_voice_assistant_speech(message)
        logger.info(f"{message}") 

    except Exception as e:
        error_message = f"Произошла ошибка при добавлении дела в список: {e}"
        core.play_voice_assistant_speech(error_message)
        logger.error(f"{error_message}")

def clear_todo_list(core:VACore, phrase: str):

    TODO_FILE_PATH = get_todo_file_path(core)  
    
    if not os.path.exists(TODO_FILE_PATH):
        message = "Файл со списком дел не найден, нечего очищать."
        core.play_voice_assistant_speech(message)
        logger.info(f"{message}")
        return

    try:
        
        with open(TODO_FILE_PATH, 'w', encoding='utf-8') as f:
            pass 

        message = "Список дел очищен."
        core.play_voice_assistant_speech(message)
        logger.info(f"{message}") 

    except Exception as e:
        error_message = f"Произошла ошибка при очистке списка дел: {e}"
        core.play_voice_assistant_speech(error_message)
        logger.error(f"{error_message}")

