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
import pygsheets


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


def get_sheet(sheet_id):
    c = pygsheets.authorize(service_file=GOOGLE_CREDENTIALS)
    sheet = c.open_by_key(sheet_id)
    return sheet.worksheet_by_title('Sheet1')


class Sheet(object):

    def __init__(self, sheet=SHEET):
        self.worksheet = get_sheet(sheet)
        self.columns = self.worksheet.row(1)
        self.refresh()

    def refresh(self):
        self.rows = self.worksheet.get_all_records()
        self.rows_list = self.worksheet.all_values()[1:]

    def has_info(self, row):
        return any(bool(row.get(col, ''))
                   for col in self.columns[5:])

    def get_dogs(self):
        for row in self.rows:
            if row['Reviewed by'] == '':
                yield (row['Dog'], self.has_info(row))


sheet = Sheet()

@app.route('/')
def main():
    sheet.refresh()
    dogs = sorted(list(sheet.get_dogs()))
    return render_template('main.html', dogs=dogs)

@socketio.on('submit', namespace='/apa')
def submit(message):
    try:
        print(message, file=sys.stderr)
        emit('done', namespace='/apa')
    except:
        emit('error', {'foo': 3}, namespace='/apa')

@socketio.on('connect', namespace='/apa')
def ws_conn():
    print('Connected {}'.format(request.sid))

@socketio.on('disconnect', namespace='/apa')
def ws_disconn():
    print('Disconnected {}'.format(request.sid))

@app.route('/download', methods=['POST'])
def download():
    return send_from_directory(directory='.', filename='out.pdf')


if __name__ == '__main__':
    socketio.run(app, "0.0.0.0", port=80)
