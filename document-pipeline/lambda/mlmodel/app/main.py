
import json
import os
import sys
import time

import app
from utils import add_handler, init_logger

sys.path.append('./')


def app_decorator(app_handler):
    def wrapper(*args, **kwargs):
        start = time.process_time()
        log = init_logger()
        log = add_handler(log)
        result = app_handler(*args, **kwargs)
        end = time.process_time()
        log.info('{0} is executed in {1}'.format(
            app_handler.__name__, end-start))
        return result
    return wrapper


@app_decorator
def handler(event, context):
    return app.handler(event, context)
