from flask import Flask
from ooi_instrument_agent.views import page
from gevent.monkey import patch_all

# We're using the gevent worker from gunicorn
# So, monkey patch all prior to creating the app
patch_all()
app = Flask(__name__)

# Register the instrument api at /instrument
app.register_blueprint(page, url_prefix='/instrument')