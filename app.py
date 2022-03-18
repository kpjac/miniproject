from decimal import InvalidOperation
from time import timezone
from flask import Flask, redirect, abort, flash, request, render_template, session
from markupsafe import escape
from models import db
from models import CoinModel
import httpx
from datetime import datetime, timedelta, timezone

from requests.exceptions import ConnectionError, Timeout, TooManyRedirects

app = Flask(__name__)
app.config.update(
    TESTING=True,
    SECRET_KEY='192b9bdd22ab9e34dsai43sdf9834fdsjk349fd91bbf5dc987d54727823bcbf'
)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgres://yqzhacpyrwvqep:af7d32705ce5288382f403e4f41411a2d1e0d81018bad511a05c21105af20353@ec2-18-210-191-5.compute-1.amazonaws.com:5432/d3q67rb49kjoie'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


@app.before_first_request
def create_table():
    db.create_all()
    db.session.commit()


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


@app.route("/<name>")
def hello(name):
    return f"Hello, {escape(name)}!"


@app.route('/add', methods=['GET', 'POST'])
async def add():
    if request.method == 'GET':
        return render_template('addpage.html')

    if request.method == 'POST':
        coin_symbol = request.form['coin_symbol'].upper()
        if CoinModel.query.filter_by(coin_symbol=coin_symbol).first() is not None:
            return render_template('addpage.html', error='This coin is already tracked')
        amount = request.form['amount']
        if float(amount) <= 0:
            return render_template('addpage.html', error='Amount may not be negative')
        if ',' in coin_symbol:
            return render_template('addpage.html', error='You may only add one coin at a time')
        try:
            coin_data = await fetchData(coin_symbol)
            coin_name = coin_data['name']
            latest_usd = coin_data['usd_latest']
            change_24h = coin_data['change_24h']
            change_7d = coin_data['change_7d']
            change_90d = coin_data['change_90d']
        except InvalidOperation:
            return render_template('addpage.html', error='A coin with this symbol could not be found')
        
        coin = CoinModel(coin_symbol=coin_symbol,
                         coin_name=coin_name, amount=amount, latest_usd=latest_usd,
                         change_24h=change_24h, change_7d=change_7d, change_90d=change_90d)
        db.session.add(coin)
        db.session.commit()
        flash('Your coin was added successfully')
        return redirect('/tracker')


@app.route('/tracker')
async def RetrieveDataList():
    coins = CoinModel.query.all()
    if coins:
        total_value = 0.0
        if session.get('last_price_update') is None or datetime.now(timezone.utc) - timedelta(minutes=10) > session.get('last_price_update'):
            await updateAllPrices(coins)
        for coin in coins:
            coin.value = coin.amount * coin.latest_usd
            total_value += coin.value
        return render_template('tracker.html', coins=coins, total_value=total_value)
    else:
        return render_template('tracker.html', coins=False)


@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    coin = CoinModel.query.filter_by(id=id).first()
    if request.method == 'POST':
        if float(request.form['amount']) < 0.000000000001:
            return redirect(f'/delete/{id}')
        if coin:
            coin.amount = request.form['amount']
            db.session.commit()
            return redirect('/tracker')
        return f"Coin with id = {id} does not exist"

    return render_template('update.html', coin=coin)


@app.route('/delete/<int:id>', methods=['GET'])
def delete(id):
    coin = CoinModel.query.filter_by(id=id).first()
    if coin:
        db.session.delete(coin)
        db.session.commit()
        flash('Your coin was deleted')
        return redirect('/tracker')
    abort(404)


async def fetchData(symbol):
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
    parameters = {
        'symbol': symbol
    }

    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': '51e1a1a9-8b2b-4e61-99d3-8a6756dfc08c',
    }

    # session = Session()
    # session.headers.update(headers)

    try:
        async with httpx.AsyncClient() as client:
            client.headers.update(headers)
            response = await client.get(url, params=parameters)
            if response.status_code == 200:
                jsonResponse = response.json()
                d = dict()
                d['name'] = jsonResponse["data"][symbol]["name"]
                d['usd_latest'] = jsonResponse["data"][symbol]["quote"]["USD"]["price"]
                d['change_24h'] = jsonResponse["data"][symbol]["quote"]["USD"]["percent_change_24h"]
                d['change_7d'] = jsonResponse["data"][symbol]["quote"]["USD"]["percent_change_7d"]
                d['change_90d'] = jsonResponse["data"][symbol]["quote"]["USD"]["percent_change_90d"]
                return d
            if response.status_code == 400:
                raise InvalidOperation('No coin could be found with this symbol')
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)

@app.post('/refresh')
async def refreshPrices():
    coins = CoinModel.query.all()
    await updateAllPrices(coins)
    return redirect('/tracker')

async def updateAllPrices(coins):
    url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'
    symbols = list()
    for coin in coins:
        symbols.append(coin.coin_symbol)
    parameters = {
        'symbol': ','.join(symbols)
    }

    headers = {
        'Accepts': 'application/json',
        'X-CMC_PRO_API_KEY': '51e1a1a9-8b2b-4e61-99d3-8a6756dfc08c',
    }

    try:
        async with httpx.AsyncClient() as client:
            client.headers.update(headers)
            response = await client.get(url, params=parameters)
            if response.status_code == 200:
            # data = json.loads(response.text)
                jsonResponse = response.json()
                for coin in coins:
                    coin_for_update = CoinModel.query.filter_by(id=coin.id).first()
                    coin_for_update.latest_usd = jsonResponse["data"][coin.coin_symbol]["quote"]["USD"]["price"]
                    coin_for_update.change_24h = jsonResponse["data"][coin.coin_symbol]["quote"]["USD"]["percent_change_24h"]
                    coin_for_update.change_7d = jsonResponse["data"][coin.coin_symbol]["quote"]["USD"]["percent_change_7d"]
                    coin_for_update.change_90d = jsonResponse["data"][coin.coin_symbol]["quote"]["USD"]["percent_change_90d"]
                    db.session.commit()
                session['last_price_update'] = datetime.now(timezone.utc)
            if response.status_code == 400:
                raise InvalidOperation('No coin could be found with this symbol')
    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)
