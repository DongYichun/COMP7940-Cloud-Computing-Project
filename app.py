import requests
import re
import random
import configparser
from bs4 import BeautifulSoup
from flask import Flask, request, abort
from imgurpython import ImgurClient

from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import *
from covid import Covid
from datetime import datetime
import pytz

app = Flask(__name__)
config = configparser.ConfigParser()
config.read("config.ini")

line_bot_api = LineBotApi(config['line_bot']['Channel_Access_Token'])
handler = WebhookHandler(config['line_bot']['Channel_Secret'])
client_id = config['imgur_api']['Client_ID']
client_secret = config['imgur_api']['Client_Secret']
album_id = config['imgur_api']['Album_ID']
API_Get_Image = config['other_api']['API_Get_Image']


## Initialize COVID API
covid = Covid(source="worldometers")
all_countries_and_continents = covid.list_countries()
all_countries = all_countries_and_continents[8:]
first_part_countries = all_countries[:100]
second_part_countries = all_countries[100:]

statisticsQuery = [
    'corona now',
    'corona countries',
    'corona countries more'
]



@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    # print("body:",body)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'ok'
    
def watch_for_symptoms():
    target_url = 'https://www.cdc.gov/coronavirus/2019-ncov/symptoms-testing/symptoms.html'
    wfs = requests.session()
    requests.packages.urllib3.disable_warnings()
    watchfor = wfs.get(target_url, verify=False)
    bs = BeautifulSoup(watchfor.text, 'html.parser')
    symptom_all = bs.find('ul',{'class':'false'})
    symptom = symptom_all.find_all('li')
    content = 'You need to pay attention to the following symptoms:\n'
    for i in symptom:
       sym = i.get_text().strip()
       content = content + sym +'\n'
    return content

def apple_news():
    target_url = 'https://tw.appledaily.com/new/realtime'
    print('Start parsing appleNews....')
    rs = requests.session()
    res = rs.get(target_url, verify=False)
    soup = BeautifulSoup(res.text, 'html.parser')
    content = ""
    for index, data in enumerate(soup.select('.rtddt a'), 0):
        if index == 4:
            return content
        link = data['href']
        content += '{}\n\n'.format(link)
    return content


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    print("event.reply_token:", event.reply_token)
    print("event.message.text:", event.message.text)
    command = (event.message.text.lower()).strip()

    if command == "news":
        content = apple_news()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=content))
        return 0
    
    if command == "symptom":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="Common signs of infection include respiratory symptoms, fever, cough, shortness of breath and breathing difficulties."))
        return 0

    if command == "main symptom":
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="Mainly for dry cough, fever and fatigue"))
        return 0
        
    if command == "watch for symptoms":
        watch_for = watch_for_symptoms()
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=watch_for))
        return 0
        
    if (command in statisticsQuery) or ('corona country -' in command): 
        command = (event.message.text).lower()
        msg = handle_statistics_query(command)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(msg)
        )
        return 0

    if command == "start":
        buttons_template = TemplateSendMessage(
            alt_text='start template',
            template=ButtonsTemplate(
                title='Services',
                text='Please Select',
                thumbnail_image_url='https://i.imgur.com/xQF5dZT.jpg',
                actions=[
                    MessageTemplateAction(
                        label='News',
                        text='news'
                    ),
                    MessageTemplateAction(
                        label='COVID-19 now',
                        text='corona now'
                    ),
                    MessageTemplateAction(
                        label='Symptom',
                        text='symptom'
                    ),
                    MessageTemplateAction(
                        label='Main Symptom',
                        text='main symptom'
                    ),
                ]
            )
        )
        line_bot_api.reply_message(event.reply_token, buttons_template)
        return 0
    line_bot_api.reply_message(event.reply_token, buttons_template)

def handle_statistics_query(command):
    tz_HK = pytz.timezone('Asia/Hong_Kong') 
    datetime_HK = datetime.now(tz_HK)
    today = datetime_HK.strftime("%Y-%m-%d %H:%M") + "HKT"
    msgHead = '<As of ' + today + '> \n'

    if command == "corona now":
        msg = msgHead + fetch_corona_now_msg()
        return msg
    elif command == "corona countries":
        num_of_countries = 'Total ' + str(len(all_countries)) + ' countries are affected\n'
        msg =  msgHead + num_of_countries + 'List of countries affected: \n ' + ', '.join(first_part_countries) + ' \n ' + ' \nSend "corona countries more" to load rest of countries'
        return msg
    elif command == "corona countries more":
        num_of_countries = 'Total ' + str(len(all_countries)) + ' countries are affected\n'
        msg = msgHead + num_of_countries + 'List of countries affected: \n ' + ', '.join(second_part_countries)
        return msg
    elif 'corona country -' in command:
        country = (''.join(command[16:])).strip()
        if (country in all_countries):
            country_stat = covid.get_status_by_country_name(country)
            country_indicator = 'Latest COVID-19 Statistics in ' + country.upper() + ' : \n'
            msg = msgHead + country_indicator + '{:,}'.format(country_stat['confirmed']) + ' confirmed cases \n' + '{:,}'.format(country_stat['active']) + ' active cases \n' + '{:,}'.format(country_stat['recovered']) + ' recovered cases \n' + '{:,}'.format(country_stat['deaths']) + ' death cases'  
            
            return msg
        else:
            msg = 'Can\'t find country name "' + country.upper() + '" , please try again'
            return msg

def fetch_corona_now_msg():
    total_active_cases = covid.get_total_active_cases()
    total_confirmed_cases = covid.get_total_confirmed_cases()
    total_recovered_cases = covid.get_total_recovered()
    total_deaths = covid.get_total_deaths()

    return '{:,}'.format(total_confirmed_cases) + ' confirmed cases \n' + '{:,}'.format(total_active_cases) + ' active cases \n' + '{:,}'.format(total_recovered_cases) + ' recovered cases \n' + '{:,}'.format(total_deaths) + ' death cases \n' + '\n' +'\n' + 'Send "Corona country -name of country" to find out country wide information\n' +  '\n' + '\n' + 'Send "Corona countries" for exploring influence of COVID-19'

def fetch_corona_country(countryName):
    return covid.get_status_by_country_name(countryName)

if __name__ == '__main__':
    app.run()
