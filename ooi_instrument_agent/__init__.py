from flask import Flask
from ooi_instrument_agent.views import page
from gevent.monkey import patch_all

patch_all()
app = Flask(__name__)
app.register_blueprint(page, url_prefix='/instrument')