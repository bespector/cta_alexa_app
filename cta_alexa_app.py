import os
from flask import Flask, render_template
from flask_ask import Ask, request, session, question, statement
from lxml import html
from collections import OrderedDict
import requests, bs4
from datetime import datetime
app = Flask(__name__)

ask = Ask(app, "/")
from twilio.rest import Client
import requests

directions = {"North":1,
              "East":1,
              "South":5,
              "West":5}

train_lines = {"Red":"Red",
               "Purple":"P",
               "Brown":"Brn",
               "Orange":"Org",
               "Green":"G",
               "Blue":"Blue",
               "Yellow":"Y",
               "Pink":"Pink"}

baseurl = 'http://lapi.transitchicago.com/api/1.0/ttarrivals.aspx?'
API_KEY = os.environ['CTA_API_KEY']
HOME_STATION = '40530'
DIRECTION = None
SEND_TEXT = False

def get_train_stop_data():
    stop_url = "https://data.cityofchicago.org/resource/8mj8-j3c4.json"
    r = requests.get(stop_url)
    stop_data = r.json()
    return OrderedDict((i['stop_name'], i['map_id']) for i in stop_data)

def get_arrival_time(time,time_format = "%Y-%m-%dT%H:%M:%S"):
    return str(round((datetime.strptime(time, time_format)-  datetime.now()).total_seconds()/60,1))
    
def get_train_data(map_id=HOME_STATION, direction=DIRECTION, line=None, trainid=None):
    direction = [directions[direction]] if direction else [1,5]
    line = [train_lines[line]] if line else train_lines.values()
    url = "{}mapid={}&key={}&outputType=JSON".format(baseurl, map_id, API_KEY)
    response = requests.get(url)
    if(response.status_code in [200, 201]):
        trains = response.json()
    else:
        return None
    if(trainid):
        times = OrderedDict((i['rn'],get_arrival_time(i['arrT'])) for i in trains['ctatt']['eta'] if 
                     (int(i['trDr']) in direction and 
                      (i['rt'] in line) and 
                      (i['rn'] in trainid)))
    else:
        times = OrderedDict((i['rn'],get_arrival_time(i['arrT'])) for i in trains['ctatt']['eta'] if
                     (int(i['trDr']) in direction and
                      i['rt'] in line))
    return times

def _send_sms_notification(to, message_body, callback_url=None):
    account_sid = os.environ['TWILIO_ACCOUNT_SID']
    auth_token = os.environ['TWILIO_AUTH_TOKEN']
    twilio_number = os.environ['TWILIO_NUMBER']
    client = Client(account_sid, auth_token)
    client.messages.create(to=to,
                           from_=twilio_number,
                           body=message_body)

@ask.launch
def launch():
    global HOME_STATION
    try:
        key = next(key for key, value in get_train_stop_data().items() if value == HOME_STATION)
    except StopIteration:
        statement("There was a problem locating your home station")
    msg = 'Hello, welcome to Brians Alexa App. Would you like the next trains from {}?'.format(key.split("(")[0])
    return question(msg)

@ask.intent("SendUpdatesIntent")
def send_updates():
    global HOME_STATION,DIRECTION,SEND_TEXT
    import time
    my_number = os.environ['TWILIO_TO_NUMBER']
    max_iter = 10
    i=0
    next_trains = get_train_data(map_id=HOME_STATION, direction=DIRECTION)
    try:
        train = next(iter(next_trains))
        while(i<max_iter):
            msg = "Next trains arriving in ",next_trains.values()[0]
            if(SEND_TEXT):
                _send_sms_notification(my_number, msg)
            else:
                print msg
            time.sleep(60)
            next_trains = get_train_data(map_id=HOME_STATION, direction=DIRECTION, trainid=train)
            train = next(iter(next_trains))
            i+=1
    except StopIteration:
        print "stop iteration"
    return statement("None")

@ask.intent("YesIntent")
def get_trains():
    global HOME_STATION, DIRECTION
    next_trains = get_train_data(map_id=HOME_STATION, direction=DIRECTION).values()
    to_return = "The next train is arriving in "+ " minutes, ".join(next_trains[:-1]) + \
    " and " + next_trains[-1] + " minutes."
    
    return question(to_return + "Whould you like text updates? Say Send Updates to enable this feature.")

@ask.intent("SetHomeStation")
def set_home(home):
    global HOME_STATION
    HOME_STATION = home
    print home
    return statement("Home station set as:" + home)

@ask.intent("SetDirection")
def set_direction(direction):
    global DIRECTION
    DIRECTION = direction
    print direction
    return statement("Direction set as: "+ direction)

@ask.intent("AMAZON.FallbackIntent")
def i_donno():
    return statement("This is the fallback intent. Try something else...")

if __name__ == '__main__':
    app.run(debug=True)




