from flask_sqlalchemy import SQLAlchemy
 
db = SQLAlchemy()
 
class CoinModel(db.Model):
    __tablename__ = "table"
 
    id = db.Column(db.Integer, primary_key=True)
    coin_symbol = db.Column(db.String())
    coin_name = db.Column(db.String())
    amount = db.Column(db.Float())
    latest_usd = db.Column(db.Float())
    change_24h = db.Column(db.Float())
    change_7d = db.Column(db.Float())
    change_90d = db.Column(db.Float())
 
    def __init__(self, coin_symbol,coin_name,amount,latest_usd,change_24h,change_7d,change_90d):
        self.coin_symbol = coin_symbol
        self.coin_name = coin_name
        self.amount = amount
        self.latest_usd = latest_usd
        self.change_24h = change_24h
        self.change_7d = change_7d
        self.change_90d = change_90d
 
    def __repr__(self):
        return f"{self.coin_symbol}({self.coin_name}):{self.amount}, {self.latest_usd}USD"