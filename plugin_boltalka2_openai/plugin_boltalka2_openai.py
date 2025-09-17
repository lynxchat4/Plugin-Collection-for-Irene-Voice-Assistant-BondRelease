# Болталка с openai - версия 2
# author: Vladislav Janvarev

from vacore import VACore

import json
import os
import openai
import requests

# Глобальная переменная для управления сессией
active_session = False

#proxy = 'http://127.0.0.1:10809'

#os.environ['http_proxy'] = proxy 
#os.environ['HTTP_PROXY'] = proxy
#os.environ['https_proxy'] = proxy
#os.environ['HTTPS_PROXY'] = proxy

# ---------- from https://github.com/stancsz/chatgpt ----------
class ChatApp:
    def __init__(self, model="gpt-4.1-mini", load_file='', system=''):
        # Setting the API key to use the OpenAI API
        self.model = model
        self.messages = []
        if system != '':
            self.messages.append({"role": "system", "content" : system})
        if load_file != '':
            self.load(load_file)

    def chat(self, message):
        if message == "exit":
            self.save()
            os._exit(1)
        elif message == "save":
            self.save()
            return "(saved)"
        self.messages.append({"role": "user", "content": message})
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=self.messages,
#            temperature=0.8,
#            n=1,
#            max_tokens=300,
        )
        self.messages.append({"role": "assistant", "content": response["choices"][0]["message"].content})
        return response["choices"][0]["message"]
    def save(self):
        try:
            import time
            import re
            import json
            ts = time.time()
            json_object = json.dumps(self.messages, indent=4)
            filename_prefix=self.messages[0]['content'][0:30]
            filename_prefix = re.sub('[^0-9a-zA-Z]+', '-', f"{filename_prefix}_{ts}")
            with open(f"models/chat_model_{filename_prefix}.json", "w") as outfile:
                outfile.write(json_object)
        except:
            os._exit(1)

    def load(self, load_file):
        with open(load_file) as f:
            data = json.load(f)
            self.messages = data

modname = os.path.basename(__file__)[:-3] # calculating modname

# функция на старте
def start(core:VACore):
    manifest = {
        "name": "Болталка с OpenAI v2 - на ChatGPT с сохранением контекста",
        "version": "2.0",
        "require_online": True,
        "description": "После указания apiKey позволяет вести диалог с ChatGPT.\n"
                       "Голосовая команда: поболтаем|поговорим",
        "url": "https://github.com/janvarev/irene_plugin_boltalka2_openai",

        "options_label": {
            "apiKey": "API-ключ OpenAI для доступа к ChatGPT", #
            "apiBaseUrl": "URL для OpenAI (нужен, если вы связываетесь с другим сервером, эмулирующим OpenAI)",  #
            "system": "Вводная строка, задающая характер ответов помощника."
        },

        "default_options": {
            "apiKey": "", #
            "apiBaseUrl": "",  #
            "system": "Ты - Ирина, голосовой помощник, помогающий человеку. Давай ответы кратко и по существу."
        },

        "commands": {
            "поболтаем|поговорим": run_start,
        }
    }
    return manifest

def start_with_options(core:VACore, manifest:dict):
    pass

def run_start(core:VACore, phrase:str):
    global active_session
    
    options = core.plugin_options(modname)

    if options["apiKey"] == "" and options["apiBaseUrl"] == "":
        core.play_voice_assistant_speech("Нужен ключ апи для доступа к опенаи")
        return

    openai.api_key = options["apiKey"]
    if options["apiBaseUrl"] != "":
        openai.api_base = options["apiBaseUrl"]

    core.chatapp = ChatApp(system=options["system"]) # создаем новый чат
    
    # Начинаем новую сессию
    active_session = True
    
    if phrase == "":
        core.play_voice_assistant_speech("О чем ты хочешь поговорить?")
        core.context_set(boltalka, 60)
    else:
        boltalka(core,phrase)

def handle_exit_command(core:VACore, phrase:str):
    global active_session
    exit_commands = ["отмена", "пока", "закончили", "закончим", "хватит", "стоп"]
    
    if any(cmd in phrase.lower() for cmd in exit_commands):
        active_session = False
        core.say("До св+язи!")
        core.context_set(boltalka, 1)
        return True
    return False


def boltalka(core:VACore, phrase:str):
    global active_session

    # Проверяем команды выхода ПЕРВЫМИ
    if handle_exit_command(core, phrase):
        return
    
    # Если сессия не активна (после команды выхода), не обрабатываем запрос
    if not active_session:
        return

    try:
        response = core.chatapp.chat(phrase) #generate_response(phrase)
        print(response)
        core.say(response["content"])
        
        # Устанавливаем контекст только если сессия еще активна
        if active_session:
            core.context_set(boltalka, 60)

    except:
        import traceback
        traceback.print_exc()
        core.play_voice_assistant_speech("Проблемы с доступом к апи. Посмотрите логи")