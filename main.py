import aiosmtplib
import asyncio
import os
import requests
import re

from datetime import date
from dotenv import load_dotenv
from email.message import EmailMessage
from PIL import Image
from typing import Tuple

load_dotenv()

ACCU_API_KEY = os.environ.get('ACCU_API_KEY')
EMAIL_ORIGIN = os.environ.get('EMAIL_ORIGIN')
EMAIL_DESTINATIONS = os.environ.get('EMAIL_DESTINATIONS').split(', ')
GMAIL_PWORD = os.environ.get('GMAIL_PWORD')
LOCATION_KEY = os.environ.get('LOCATION_KEY')
NYC_PRIMARY_KEY = os.environ.get('NYC_PRIMARY_KEY')

ACCU_URL = 'http://dataservice.accuweather.com/'
HOST = "smtp.gmail.com"
NYC_URL = 'https://api.nyc.gov/public/api/'


def find_location_key(location):
    """Takes location and gets location key from accuweather site. Key is added to '.env' file"""
    url = f'{ACCU_URL}locations/v1/cities/search'
    context = {
        'apikey': ACCU_API_KEY,
        'q': location
    }
    response = requests.get(url, context)
    location_info = response.json()
    location_key = location_info[0]['Key']
    with open('.env', 'a') as f:
        f.write(f"\n\n# Location key for AccuWeather searches\nLOCATION_KEY = '{location_key}'")
    return location_key


def get_current_conditions(location_key):
    """Takes location key and returns current weather conditions"""
    url = f'{ACCU_URL}currentconditions/v1/{location_key}'
    context = {
        'apikey': ACCU_API_KEY,
        'details': True,
    }
    response = requests.get(url, context)
    return response.json()


def get_alert_time_conditions(location_key):
    """Takes location key and returns weather conditions for specified hours"""
    url = f'{ACCU_URL}forecasts/v1/hourly/12hour/{location_key}'
    context = {
        'apikey': ACCU_API_KEY,
        'details': True,
    }
    response = requests.get(url, context)
    hourly_json = response.json()
    if response.status_code == 200:
        weather_message = ''
        for entry in hourly_json:                   
            # Pull the hour from the json data to compare it to desired times
            time = entry['DateTime'].split('T')[1].split(':')[0]
            # Specified hours are 9 a.m. and 5 p.m.
            if time == '09' or time == '17':
                temperature = round(entry['Temperature']['Value'])
                real_feel = round(entry['RealFeelTemperature']['Value'])
                wind = round(entry['Wind']['Speed']['Value'])
                wind_gusts = round(entry['WindGust']['Speed']['Value'])
                precipitation = entry['PrecipitationProbability']
                time_num = int(time)
                if time_num > 12:
                    time = f'{time_num - 12} p.m.'
                elif time_num < 12:
                    time = f'{time} a.m.'
                weather_text = f'Weather at {time}:\nTemp {temperature}\xb0\nFeel {real_feel}\xb0\nWind {wind} mph\nGusts {wind_gusts} mph\nPrecip {precipitation}%\n\n'
                weather_message = weather_message + weather_text
        weather_message = ''.join(weather_message)
        return weather_message      
    else:
        code = hourly_json['Code']
        message = hourly_json['Message']
        error = f'Error code: {code}\nMessage: {message}\n\n'
        return error


def alternate_parking_status():
    today = date.today()
    alternate_parking_url = f'{NYC_URL}GetCalendar?fromdate={today}&todate={today}'
    context = {
        'Cache-Control': 'no-cache',
        'Ocp-Apim-Subscription-Key': NYC_PRIMARY_KEY
    }
    response = requests.get(alternate_parking_url, headers=context)
    park_json = response.json()
    parking_status = park_json['days'][0]['items'][0]['status']
    if parking_status == "IN EFFECT":
        return 'ASP is in effect today.'
    elif parking_status == "SUSPENDED":
        return 'ASP is NOT in effect today.'
    

async def send_email(*args: str) -> Tuple[dict, str]:
    host, email, pword, msg, subj = args

    # build message
    message = EmailMessage()
    message["From"] = email
    message["To"] = EMAIL_DESTINATIONS
    message["Subject"] = subj
    message.set_content(msg)
    print(message)

    #send
    send_kws = dict(username=email, password=pword, hostname=host, port=587, start_tls = True)
    res = await aiosmtplib.send(message, **send_kws)
    if not re.search(r"\sOK\s", res[1]):
        print("Sending email failed.")
    else:
        print("Sending email succeeded")
    return res


location_key = LOCATION_KEY
if location_key == None:
    location = input('There is no location specified. Please add a zipcode or City, State: ')
    location_key = find_location_key(location)
weather = get_alert_time_conditions(location_key)
park = alternate_parking_status()
email_text = "Good Morning!\n\nHere are today's commute weather conditions:\n\n" + weather + park + "\n\nHave a good one!"

if __name__ == "__main__":
    _host = HOST
    _email = EMAIL_ORIGIN
    _pword = GMAIL_PWORD
    _msg = email_text
    _subj = "Morning Announcements"
    coro = send_email(_host, _email, _pword, _msg, _subj)
    asyncio.run(coro)
