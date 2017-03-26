import eventlet
#eventlet.monkey_patch()

import sys
import time
import os
import socket
import json

from flask import Flask, render_template, request, redirect, flash
from flask import send_from_directory
from flask_socketio import SocketIO, send, emit
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField
from wtforms.validators import DataRequired


def get_env_vars(*names):
    missing = []
    for name in names:
        try:
            yield os.environ[name]
        except KeyError:
            missing.append(name.upper())
    if missing:
        print('Environment variables {0} are needed'.format(', '.join(missing)))
        sys.exit(1)


SHEET, GOOGLE_CREDENTIALS = get_env_vars('SHEET', 'GOOGLE_CREDENTIALS')


app = Flask(__name__)

app.config.update(
    DEBUG = True,
    SECRET_KEY = 'apa!'
)

socketio = SocketIO(app, logger=True, engineio_logger=True)


def cards_read():
    line = cards.readline()
    print(f'cards_read: {line}')
    return json.loads(line)

def cards_write(data):
    cards.write(json.dumps(data) + '\n')
    cards.flush()


@app.route('/')
def main():
    return render_template(
        'main.html')

@socketio.on('connect', namespace='/apa')
def ws_conn():
    print('Connected {}'.format(request.sid))

@socketio.on('disconnect', namespace='/apa')
def ws_disconn():
    print('Disconnected {}'.format(request.sid))

@socketio.on('refresh_dogs', namespace='/apa')
def refresh_dogs():
    def _bg(room):
        cards_write({'tag': 'refresh'})
        result = cards_read()
        cards_write({'tag': 'all_dogs_names'})
        result = cards_read()
        socketio.emit('dogs', {'names': result['all_dogs_names']},
                      namespace='/apa', room=room)
    eventlet.spawn(_bg, request.sid)

@socketio.on('check_download', namespace='/apa')
def check_download(message):
    def _bg(room):
        cards_write({'tag': 'refresh'})
        result = cards_read()
        print('got message: {}'.format(message))
        cards_write({
            'tag': 'generate',
            'names': message['selected']})
        result = cards_read()
        if (result['status'] == 'error'
               and result['exception'] == 'PictureNotFound'):
            socketio.emit('picture_not_found',
                          {'for': result['args']},
                          namespace='/apa', room=room)
        elif (result['status'] == 'error'
              and result['exception'] == 'KeyError'):
            socketio.emit('dog_not_found',
                        {'for': result['args']},
                        namespace='/apa', room=room)
        elif (result['status'] == 'error'
              and result['exception'] == 'Exception'):
            socketio.emit('general_exception',
                        {'for': result['args']},
                        namespace='/apa', room=room)
        else:
            socketio.emit('do_download', namespace='/apa', room=room)

    eventlet.spawn(_bg, request.sid)

@app.route('/download', methods=['POST'])
def download():
    return send_from_directory(directory='.', filename='out.pdf')

class MyForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])


if __name__ == '__main__':
    socketio.run(app, "0.0.0.0", port=80)
