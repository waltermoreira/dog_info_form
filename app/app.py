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

activities = [
    'Car rides',
    'Cats',
    'Couch potato',
    'Do tricks',
    'Dogs',
    'Entertain myself',
    'Fetch',
    'Home alone',
    'Keep you safe',
    'Kids',
    'Out on the town',
    'Run',
    'Swim',
    'Wear outfits'
]

titles = [
    'Go for car rides',
    'Hang out with cats',
    'Be a couch potato',
    'Do tricks',
    'Play with other dogs',
    'Entertain myself',
    'Play fetch',
    'Stay home alone',
    'Keep you safe',
    'Hang out with kids',
    'Go out on the town',
    'Go for runs',
    'Go swimming',
    'Wear outfits'
]


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

    def find_row(self, dog):
        for i, row in enumerate(self.rows):
            idx = i + 2
            if row['Dog'] == dog:
                return idx
        raise DogNotFound(dog)

    def get_note(self, cell):
        data = self.worksheet.client.service.spreadsheets().get(
            spreadsheetId=self.worksheet.spreadsheet.id,
            ranges=cell,
            fields='sheets(data(rowData(values(note))))').execute()
        try:
            return data['sheets'][0]['data'][0]['rowData'][0]['values'][0]['note']
        except KeyError:
            return ''

    def set_note(self, row, col, note):
        requests = [{
            "repeatCell": {
                "range": {
                    "sheetId": self.worksheet.id,
                    "startRowIndex": row,
                    "endRowIndex": row+1,
                    "startColumnIndex": col,
                    "endColumnIndex": col+1
                },
                "cell": {
                    'note': note
                },
                "fields": "note"
            }
        }]
        self.worksheet.client.sh_batch_update(
            self.worksheet.spreadsheet.id, requests)

    def set_info(self, info):
        dog = info['dog']
        row_idx = self.find_row(dog)
        row = (self.worksheet.row(row_idx) + ['']*20)[:20]
        if row[0]:
            row[0] = '*' + row[0]
        unique = info['unique']
        person = info['person']
        row[5] += f'\n--- {person} ---:\n' + unique
        for i, (activity, title) in enumerate(zip(activities, titles)):
            # get value from row
            try:
                cur = int(row[i+6])
            except ValueError:
                cur = 0
            # get note from row
            if title in info['activities']:
                note = self.get_note(chr(71+i) + str(row_idx))
                note += f'{person}\n'
                self.set_note(row_idx-1, i+6, note)
                row[i+6] = cur + 1
        self.worksheet.update_row(row_idx, row)
        return row
        

sheet = Sheet()

class DogNotFound(Exception):
    pass

def mark(message):
    sheet.set_info(message)

@app.route('/')
def main():
    sheet.refresh()
    dogs = sorted(list(sheet.get_dogs()))
    return render_template('main.html', dogs=dogs)

@socketio.on('submit', namespace='/apa')
def submit(message):
    try:
        mark(message)
        emit('done', namespace='/apa')
    except DogNotFound as exc:
        emit('notfound', {'dog': exc.args[0]}, namespace='/apa')
    except:
        emit('error', namespace='/apa')

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
