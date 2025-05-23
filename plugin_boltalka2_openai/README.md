# Плагин для разговора с OpenAI нейросетью ChatGPT с поддержанием контекста и прокси
irene_plugin_boltalka2_openai
Протестировано с версией Home Assistant 2025.1.1 и версией Ирины от AlexeyBond 0.9.1

Версия отличается от [оригинальной] (https://github.com/janvarev/irene_plugin_boltalka2_openai) добавлениением возможности выбора прокси.
Через прокси всё отлично работает из РФ. 

У openAI есть несколько бесплатных тарифных планов, которые могут подойти 90% людей. Более того, платные тарифные планы реально не дороги и нет ежемесячной платы.
Я за месяц 1-5 запросов в день потратил 30 центов.

## Новшества в плагине
1. по умолчанию стоит самая недорогая, но достаточно хорошая модль: gpt-4o-mini-2024-07-18
2. есть поддержка контекста диалога
3. возможности выбора прокси
4. возможность задавать контекст разговора с собеседником (параметр system в конфиге).

## Установка
Скопировать plugin_boltalka2_openai.py в plugins
Установить пакет openai (pip install openai)
Запустить Ирину первый раз
После первого запуска в options/plugin_boltalka2_openai.json установить API ключ OpenAI
Использование
Команда "ирина поболтаем" или "ирина поговорим"

После этого Ирина входит в контекст, в котором все фразы пересылается опенаи - говорите что угодно, опенаи будет отвечать.

Выход из контекста автоматический или по команде "пока", "отмена".

Поддержка сторонних API совместимых с OpenAI
Поддерживает сторонние API совместимые с OpenAI.

Проверено на https://github.com/oobabooga/text-generation-webui:

Включите в TGW поддержку openai плагина (обычно запуск с параметром --extensions openai)
Установите параметр apiBaseUrl в "http://127.0.0.1:5001/v1" (будет предложено в консоли TGW после запуска). API key при этом не нужен.
Все, можно чатиться!


