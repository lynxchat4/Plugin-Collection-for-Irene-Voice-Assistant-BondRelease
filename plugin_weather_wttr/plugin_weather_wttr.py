# Погода через wttr.in  
# author: Oleg Bakharev

# TODO: Доделать, чтобы говорил какой ветер, а не скорость, и влажность

from datetime import datetime
import requests

from vacore import VACore

# местоположение
location = 'Voronezh'

# информация о плагине и начальные настройки
def start(core: VACore):
    manifest = {
        'name': 'Погода (wttr.in)',
        'version': '1.0',
        'require_online': True,

        'commands': {
            'погода|погода за окном|погода сейчас': get_weather,
            'завтра погода|прогноз на завтра|погода на завтра': get_weather_forecast1,
            'прогноз погоды|прогноз на два дня|погода на два дня': get_weather_forecast2,
        }
    }
    return manifest
 
    
# вычисляет вариант текста для конкретного числительного из набора вариантов
def compute_suffix(value: str, variants: list):
	n = int(value.strip()[-1])
	if (n == 0) or (n >= 5):
		suffix = variants[0]
	elif (n == 1):
		suffix = variants[1]
		if len(value) >= 2:
			if value.strip()[-2] == '1':
				suffix = variants[2]
	else:
		suffix = variants[2]
	return suffix
	
	
# текст прогноза погоды на основании переданных данныхъ о температуре, влажности, давлении и скорости ветра	
def forecast_text(temp: str, humidity: str, pressure: str, wind_speed: str):
#	text = 'Температура {0} {1}, Влажность {2} {3}, Ветер {6} {7} в час.'.format(
	text = 'Температура {0} {1}, Влажность {2} {3}.'.format(
			temp, compute_suffix(temp, ['градусов', 'градус', 'градуса']),
			humidity, compute_suffix(humidity, ['процентов', 'процент', 'процента']),
			pressure, compute_suffix(pressure, ['миллиметров', 'миллиметр', 'миллиметра']),
			wind_speed, compute_suffix(wind_speed, ['километров', 'километр', 'километра'])
			)
	return text

		
# запросить погоду для данного местоположения
def request_weather(location: str):
	url = 'https://wttr.in/{0}?Q?m&format=j1&lang=ru'.format(location)
	req = requests.get(url)
	return req.json()

		
# сформировать описание погоды, на основании словаря JSON
def get_weather_text(data: dict):
	
	descr = data['lang_ru'][0]['value']
	
	humidity = data['humidity']
	pressure = round(int(data['pressure']) / 1.333)
	
	if 'temp_C' in data:
		temp = data['temp_C']
	else:
		temp = data['tempC']
		
	wind_speed = data['windspeedKmph']

	return descr + '. ' + forecast_text(temp, humidity, str(pressure), wind_speed)
	
		
# получить текст для описания даты прогноза
def get_date(data: str):
	day_list = ('первое', 'второе', 'третье', 'четвёртое','пятое', 'шестое', 'седьмое', 'восьмое','девятое', 'десятое', 'одиннадцатое', 'двенадцатое','тринадцатое', 'четырнадцатое', 'пятнадцатое', 'шестнадцатое','семнадцатое', 'восемнадцатое', 'девятнадцатое', 'двадцатое','двадцать первое', 'двадцать второе', 'двадцать третье','двадцать четвёртое', 'двадцать пятое', 'двадцать шестое','двадцать седьмое', 'двадцать восьмое', 'двадцать девятое','тридцатое', 'тридцать первое')
	weekday_list = ('понедельник','вторник','среду','четверг','пятницу','субботу','воскресенье')
	month_list = ('января', 'февраля', 'марта', 'апреля', 'мая', 'июня','июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря')
	
	d = datetime.strptime(data, '%Y-%m-%d')
	day = day_list[d.day - 1]
	weekday = weekday_list[d.weekday()]
	month = month_list[d.month - 1]
	text = 'Прогноз на ' + weekday + ' с датой ' +  day + ' ' + month + ' '
	return text
	
# текущая погода
def get_weather(core: VACore, phrase: str):
	try:
		weathers = request_weather(location) 
		text = get_weather_text(weathers['current_condition'][0])
		core.play_voice_assistant_speech('Сейчас на улице ' + text)
		return
	except Exception as e:
		pass
		

# прогноз погоды на завтра	
def get_weather_forecast1(core: VACore, phrase: str):
	
	# произнести прогноз на определенное время суток
	def say_hourly_weather(daytime: str, hourly: dict):
		text = get_weather_text(hourly)
		core.play_voice_assistant_speech(daytime + text)
		
		
	try:
		core.play_voice_assistant_speech('Читаю метеосводку')
		
		weathers = request_weather(location)['weather'] # город или координаты

		for weather in weathers[:1]:
			# произнести дневной прогноз
			say_hourly_weather("Завтра ", weather['hourly'][4])
			
		return
	except Exception as e:
		pass

# прогноз погоды на два дня	
def get_weather_forecast2(core: VACore, phrase: str):
	
	# произнести прогноз на определенное время суток
	def say_hourly_weather(daytime: str, hourly: dict):
		text = get_weather_text(hourly)
		core.play_voice_assistant_speech(daytime + text)
		
		
	try:
		core.play_voice_assistant_speech('Читаю метеосводку')
		
		weathers = request_weather(location)['weather'] # город или координаты

		day_names = ["Завтра ", "Послезавтра "]
		
		for i, weather in enumerate(weathers[:2]):
			# произнести дневной прогноз
			say_hourly_weather(day_names[i], weather['hourly'][4])
			
		return
	except Exception as e:
		pass
