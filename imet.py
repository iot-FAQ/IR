import datetime
import boto3, botocore

import re
import logging
from logging.handlers import RotatingFileHandler

from bson import ObjectId
from flask import Flask, redirect, url_for, request, render_template, session, jsonify, json, Response
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from authy.api import AuthyApiClient
from pymongo import MongoClient

import gas_counter as gs
from functions import Model
from flask import Flask, render_template, request
from flask_cors import CORS, cross_origin
import base64
import os
import uuid
import boto
import boto3
from boto.s3.key import Key
from boto.s3.connection import S3Connection
import json

from config import S3_KEY, S3_SECRET, S3_BUCKET

from threading import Lock, Thread

# from app import app, api, mongo, bcr

app = Flask(__name__)
bcr = Bcrypt(app)

lock = Lock()
model = Model()
CORS(app, headers=['Content-Type'])
# client = MongoClient('localhost', 27017)    #Configure the connection to the database
# db = client.i_Met

app.config['JSON_SORT_KEYS'] = False

app.config['MONGO_DBNAME'] = 'i-met'
app.config['MONGO_URI'] = 'mongodb://Olga:olichka121@ds121289.mlab.com:21289/i-met'
app.config['CONNECT'] = False
app.config['maxPoolsize'] = 1

mongo = PyMongo(app)
app.config.from_object('config')
api = AuthyApiClient(app.config['AUTHY_API_KEY'])
app.secret_key = app.config['SECRET_KEY']

# start deleting
true_results = {1: 0, 2: 0, 3: 2, 4: 8, 5: 3, 6: 9}
# end deleting

now = datetime.datetime.now()
curr_day = now.day
curr_month = now.month
curr_year = now.year
@app.route('/api/post/callibration_points', methods = ['POST'])
def callibration_points():
    print('HERE')
    if request.method == 'POST':
        print('HERE2')
        calib = mongo.db.calibration
        caldata = request.json

        if calib.find_one({'date': str(now.date())}):
            result = calib.delete_one({'date': str(now.date())})
        calib.insert({'date': str(now.date()), str(curr_day): caldata})
        test_callib()
        pred = test_rec()
    # return json.dumps({'success':True}), 200, {'ContentType':'application/json'}
    return jsonify(pred)

def test_callib():
    import cv2
    image = cv2.imread(cv2.samples.findFile('mysite/static/test/image2.bmp'), cv2.IMREAD_GRAYSCALE)
    if image is not None:
        all_calib = mongo.db.calibration
        calib = all_calib.find_one({'date': str(now.date())})
        gs.extractDigitsFromImage(image, calib[str(curr_day)])
        gs.splitDigits(image)


@app.route("/ttest_rec")
def ttest_rec(results, index):
    from PIL import ImageOps, Image
    prediction = {}
    pred = ''
    threads = []
    # if i == 5 or i == 6:
    #     continue
    image = Image.open("mysite/static/test/c_" + str(index) + ".png")
    # image =  ImageOps.invert(image)
    temp = model.predict(image, "test")
    results[index] = str(temp["answer"])
    # prediction[i] = temp["answer"]
    # pred += str(temp["answer"])
    # pred = '0000072'
    # model.train(image, true_results[index], "test")


@app.route("/test_rec")
def test_rec():
    from PIL import ImageOps, Image
    prediction = {}
    pred = ''
    threads = []
    results = {}
    for i in range(1, 7):
        # if i == 5 or i == 6:
        #     continue
        # image = Image.open("mysite/static/test/c_" + str(i) + ".png")
        # image =  ImageOps.invert(image)
        t = Thread(target=ttest_rec, args=(results, i))
        t.start()
        threads.append(t)
        # temp = model.predict(image, "test")
        # prediction[i] = temp["answer"]
        # pred += str(temp["answer"])
        # pred = '0000072'
        # model.train(image, 2, "test")
    for j in threads:
        j.join()
    for i in range (1, 7):
        pred += results[i]
        # image = Image.open("mysite/static/test/c_" + str(i) + ".png")
        # model.train(image, true_results[i], "test")
    return pred
    # return "Trained"


@app.route("/digits", methods=["POST", "GET", 'OPTIONS'])
def index_page():
	return render_template('index_digit.html')

@app.route("/about")
def about():
	return render_template('about.html')

@app.route("/internals")
def internals():
	return render_template('internals.html')

@app.route("/models")
def models():
	return render_template('models.html')

@app.route('/hook2', methods = ["GET", "POST", 'OPTIONS'])
def predict():
	"""
	Decodes image and uses it to make prediction.
	"""
	if request.method == 'POST':
	    image_b64 = request.values['imageBase64']
	    image_encoded = image_b64.split(',')[1]
	    image = base64.decodebytes(image_encoded.encode('utf-8'))

	    prediction = model.predict(image, "hand")

	return json.dumps(prediction)

@app.route('/hook3', methods = ["GET", "POST", 'OPTIONS'])
def train():
	"""
	Decodes image and uses it to tain models.
	"""
	if request.method == 'POST':
		image_b64 = request.values['imageBase64']
		image_encoded = image_b64.split(',')[1]
		image = base64.decodebytes(image_encoded.encode('utf-8'))
		digit = request.values['digit']

		model.train(image, digit, "hand")

	return 'Trained'


@app.route('/')
def index():
    if 'user' in session:
        return render_template('index.html', url=url_for('user_cabinet'), name='Кабінет')
    return render_template('index.html', url=url_for('login'), name='Увійти')


@app.route('/login', methods=['POST', 'GET'])
def login():
    if 'user' in session:
        return redirect(url_for('user_cabinet'))
    if request.method == 'POST':
        user = mongo.db.users
        login_user = user.find_one({'email': request.form['email']})
        if login_user:
            if bcr.check_password_hash(login_user['password'], request.form['password']):
                session['user'] = request.form['email']
                return redirect(url_for('index'))
            else:
                return "Error"
    return render_template('login-page.html')


@app.route('/register', methods=['POST', 'GET'])
def register():
    type = ""
    other_type = ""
    if request.method == 'POST':
        users = mongo.db.users
        existing_user = users.find_one({'email': request.form['email']})
        if request.form['type'].lower() == 'вода':
            type = "water"
            other_type = "gas"
        if existing_user is None:
            hashpass = bcr.generate_password_hash(request.form['password'])
            users.insert(
                {'email': request.form['email'], 'password': hashpass, 'name': request.form['first-name'],
                 'surname': request.form['last-name'], 'phone': request.form['phone'], 'account_num':
                     {'type':
                         {type:
                             {request.form['counter-name']:
                                 {'date': {str(curr_year):
                                     {str(curr_month):
                                         {'month': '', str(curr_day):
                                             {}
                                            }
                                        }
                                    }
                                }
                            },
                            other_type: {"0": {'date': {"0": {'0': {'month': '', '0':{}}}}}}}}})
            return redirect(url_for('index'))

        return 'That email already exists'

    return render_template('signup-page.html')

@app.route('/future')
def future_page():
    return render_template('future-page.html')

@app.route('/calib', methods=['POST', 'GET'])
def calib():
    if request.method == 'POST':
        if request.form['exit'] == 'exit':
            logout()
            return redirect(url_for('index'))
    files = os.listdir('mysite/static/tempphoto')
    return render_template('calib.html', files=files)

@app.route('/preorder', methods=['POST', 'GET'])
def preorder():
    if request.method == 'POST':
        preorders = mongo.db.preorders
        preorder = preorders.find_one({"preorders": "preorders"})
        id = preorder['_id']
        count = int(preorder['count'])
        count += 1
        preorders.update({
            '_id': ObjectId(id)
        }, {
            '$set': {
                'count': str(count),
                str(count): {
                    'name': request.form['form-first-name'], 'surname': request.form['form-last-name'],
                    'email': request.form['form-email'], 'phone': request.form['form-phone']
                }
            }
        })
        return redirect(url_for('index'))
    if 'user' in session:
        return render_template('pre-order.html', url=url_for('user_cabinet'), name='Кабінет')
    return render_template('pre-order.html', url=url_for('login'), name='Увійти')


@app.route('/user', methods=['POST', 'GET'])
def user():
    print('i`m in user')
    if request.method == 'POST':
        print('send post')
        if request.form['exit'] == 'exit':
            logout()
            return redirect(url_for('index'))
    return render_template('user.html')


@app.route('/user_cabinet', methods=['POST', 'GET'])
def user_cabinet():
    if request.method == 'POST':
        if request.form['exit'] == 'exit':
            logout()
            return redirect(url_for('index'))
    labels = []
    values_gas = []
    # result = []
    counter = list(get_counters(session['user'], 'gas').keys())
    if counter[0] != "0":
        if check_data(session['user'], 'gas', counter[0]):
            data = get_data(session['user'], 'gas', counter[0], week_par='week')
            for key, value in data.items():
                labels.append(key)
                values_gas.append(value)
    # result.append(values)
    values_water = []
    counter = list(get_counters(session['user'], 'water').keys())
    if counter[0] != "0":
        if check_data(session['user'], 'water', counter[0]):
            data = get_data(session['user'], 'water', counter[0], week_par='week')
            for key, value in data.items():
                values_water.append(value)
    # result.append(values)
    return render_template('user-cabinet.html', values_water=values_water, values_gas=values_gas, labels=labels)


@app.route('/gas', methods=['POST', 'GET'])
def gas():
    if request.method == 'POST':
        if request.form['exit'] == 'exit':
            logout()
            return redirect(url_for('index'))
    labels = []
    values = []
    counter = list(get_counters(session['user'], 'gas').keys())
    if counter[0] != "0":
        if check_data(session['user'], 'gas', counter[0]):
            data = get_data(session['user'], 'gas', counter[0], week_par='week')
            for key, value in data.items():
                labels.append(key)
                values.append(value)
    return render_template('gas.html', values=values, labels=labels)


@app.route('/water', methods=['POST', 'GET'])
def water():
    if request.method == 'POST':
        if request.form['exit'] == 'exit':
            logout()
            return redirect(url_for('index'))
    labels = []
    values = []
    counter = list(get_counters(session['user'], 'water').keys())
    if counter[0] != "0":
        if check_data(session['user'], 'water', counter[0]):
            data = get_data(session['user'], 'water', counter[0], week_par='week')
            for key, value in data.items():
                labels.append(key)
                values.append(value)
    return render_template('water.html', values=values, labels=labels)


def logout():
    return session.pop('user', None)


def get_counters(email, type):
    users = mongo.db.users
    user = users.find_one({'email': email})
    return user['account_num']['type'][type]


def check_data(email, type, counter):
    users = mongo.db.users
    user = users.find_one({'email': email})
    if user['account_num']['type'][type][counter]['date'][str(curr_year)][str(curr_month)]['month'] == "":
        return False
    else:
        return True


@app.route('/check_user', methods=['GET'])
def check_user():
    users = mongo.db.users
    query_parameters = request.args
    email = query_parameters.get('email')
    password = query_parameters.get('password')

    user = users.find_one({'email': email})
    if user:
        if bcr.check_password_hash(user['password'], password):
            return True
        else:
            return False
    return 'Cannot find this email'


@app.route('/devices', methods=['GET'])
def get_all_devices():
  users = mongo.db.users
  output = []
  for s in users.find():
    output.append({'email' : s['email'], 'account_num' : s['account_num']})
  return jsonify({'user devices' : output})


@app.route('/devices/<email>', methods=['GET'])
def get_one_device(email):
  users = mongo.db.users
  s = users.find_one({'email' : email})
  if s:
    output = {'email' : s['email'], 'account_num' : s['account_num']}
  else:
    output = "No such email"
  return jsonify({'user devices' : output})


@app.route('/get_data', methods=['GET'])
def get_data(email_par=None, type_par=None, counter_par=None, year_par=None, month_par=None, week_par=None):
    users = mongo.db.users
    query_parameters = request.args

    email = query_parameters.get('email') or email_par
    type = query_parameters.get('type') or type_par
    counter = query_parameters.get('counter') or counter_par
    user = users.find_one({'email': email})
    if query_parameters.get('week') or week_par:
        # month = user['account_num']['type'][type][counter]['date'][str(curr_year)][str(curr_month)]
        week = dict()
        if curr_day < 7:
            last_month = user['account_num']['type'][type][counter]['date'][str(curr_year)][str(curr_month - 1)]
            for day in range(len(last_month) - 7 + curr_day, len(last_month)):
                found = re.search("{'(.+)':", str(
                    user['account_num']['type'][type][counter]['date'][str(curr_year)][str(curr_month - 1)][str(day)]))
                if found:
                    week[day] = found.group(1)
            for day in range(1, curr_day + 1):
                found = re.search("{'(.+)':", str(
                    user['account_num']['type'][type][counter]['date'][str(curr_year)][str(curr_month)][str(day)]))
                if found:
                    week[day] = found.group(1)

            if (email_par and type_par and counter_par) is not None:
                return dict(week)
            else:
                return json.dumps(dict(week), sort_keys=False)
        else:
            for day in range(curr_day - 6, curr_day + 1):
                found = re.search("{'(.+)':", str(
                    user['account_num']['type'][type][counter]['date'][str(curr_year)][str(curr_month)][str(day)]))
                if found:
                    week[day] = found.group(1)

            if (email_par and type_par and counter_par) is not None:
                return week
            else:
                return jsonify(week)
    elif query_parameters.get('month') or month_par:
        month = dict()
        for day in user['account_num']['type'][type][counter]['date'][str(curr_year)][str(curr_month)]:
            if str(day) != 'month':
                found = re.search("{'(.+)':", str(
                    user['account_num']['type'][type][counter]['date'][str(curr_year)][str(curr_month)][str(day)]))
                if found:
                    month[day] = found.group(1)
        if (email_par and type_par and counter_par) is not None:
            return month
        else:
            return jsonify(month)
    elif query_parameters.get('year') or year_par:
        year = user['account_num']['type'][type][counter]['date'][str(curr_year)]
        month = {month: year[str(month)]['month'] for month in year}
        if (email_par and type_par and counter_par) is not None:
            return dict(month)
        else:
            return jsonify(month)
    return jsonify('Error')


@app.route('/send_photo', methods=['POST'])
def send_photo():
    users = mongo.db.users
    query_parameters = request.args

    email = query_parameters.get('email')
    type = query_parameters.get('type')
    counter = query_parameters.get('counter')
    current_day = datetime.datetime.now().day

    user = users.find_one({'email': email})
    month = 'account_num.type.' + type + '.' + counter + '.date.' + str(curr_year) + '.' + str(curr_month)
    value = '270'

    from config import S3_KEY, S3_SECRET, S3_BUCKET

    S3_LOCATION = str(email) + '/' + str(type) + '/' + str(counter) + '/'
    s3 = boto3.resource('s3', aws_access_key_id=S3_KEY, aws_secret_access_key=S3_SECRET)
    photo_name = str(now.year) + '-' + str(now.month) + '-' + str(now.day) + '-' + \
            str(datetime.datetime.now().hour + 2) + '-' + str(datetime.datetime.now().minute) + '-' + str(datetime.datetime.now().second) + '.bmp'
    s3.Object(S3_BUCKET, S3_LOCATION + photo_name).put(Body=request.data, ACL="public-read")
    import io
    # import requests
    from PIL import Image
    image = Image.open(io.BytesIO(request.data))
    image.save('mysite/static/tempphoto/' + photo_name)
    image.save('mysite/static/test/image2.bmp')
    id = user['_id']
    users.update({
            '_id': ObjectId(id)
        }, {
            '$set': {
                month + '.' + str(current_day): {
                    str(value): 'https://' + S3_BUCKET + '.s3.amazonaws.com/' + S3_LOCATION + str(now.year) + '-' + str(now.month) + '-' + str(current_day) + '-' + str(datetime.datetime.now().time) + '.bmp'
                }
            }
        })
    return Response('Uploaded file successfully', status=200)


@app.route('/get_photo', methods=['GET'])
def get_photo():
    # sum_month = int(
    #     user['account_num']['type'][type][counter]['date'][str(curr_year)][str(curr_month)]['month'] or 0) + int(value)
    # id = user['_id']
    # if query_parameters.get('photo'):
    #     users.update({
    #         '_id': ObjectId(id)
    #     }, {
    #         '$set': {
    #             month + ".month": str(sum_month),
    #             month + '.' + str(curr_day): {
    #                 str(value): request.data
    #             }
    #         }
    #     })

        import io
        import requests
        from PIL import Image
        print(S3_KEY)
        print(S3_SECRET)
        print(S3_BUCKET)
        response = requests.get('https://i-met.s3.amazonaws.com/alex@gmail.com/gas/3663434534/2018-9-29.bmp')
        image = Image.open(io.BytesIO(response.content))
        image.save("image.bmp")

        return jsonify('Success')


def create_img():
    users = mongo.db.users
    user = users.find_one({'email': "alex@gmail.com"})
    f = user['account_num']['type']['gas']['3663434534']['date'][str(curr_year)][str(curr_month)][str(curr_day)]['100']
    bmp_file = open("image.bmp", "wb")
    bmp_file.write(f)
    bmp_file.close()

@app.route('/meter')
def meter():
    return render_template('meter.html')


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1]

UPLOAD_FOLDER = 'public-uploads'
import os
from werkzeug.utils import secure_filename

@app.route('/photo', methods=['GET', 'POST', 'DELETE'])
def photo():
    f = request.files['image.bmp']
    if f and allowed_file(f.filename):
        absolute_file = os.path.abspath('static' + f.filename)
        filename = secure_filename(absolute_file)
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return Response('Uploaded file successfully', status=200)
    return redirect(url_for('meter'))

# @app.route('/photo', methods=['GET', 'POST', 'DELETE'])
# def photo():
#     return Response(status=200)


@app.route('/update_data', methods=['PUT'])
def update_data():
    users = mongo.db.users
    query_parameters = request.args

    email = query_parameters.get('email')
    user = users.find_one({'email': email})
    return True


if __name__ == '__main__':
    logHandler = RotatingFileHandler('info.log', maxBytes=1000, backupCount=1)

    # set the log handler level
    logHandler.setLevel(logging.DEBUG)

    # set the app logger level
    app.logger.setLevel(logging.DEBUG)

    app.logger.addHandler(logHandler)
    app.run(debug=True)

