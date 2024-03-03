from dotenv import load_dotenv
from pynput import keyboard
from pynput.keyboard import Key

import logging
import os
import queue
import sqlalchemy
import sys
import threading


MODIFIERS = {
    Key.shift, Key.shift_l, Key.shift_r,
    Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr,
    Key.ctrl, Key.ctrl_l, Key.ctrl_r,
    Key.cmd, Key.cmd_l, Key.cmd_r,
}

TABLE = sqlalchemy.Table(
    'keyboard_monitor',
    sqlalchemy.MetaData(),
    sqlalchemy.Column('hits', sqlalchemy.String),
    sqlalchemy.Column('ts', sqlalchemy.DateTime),
)

if __name__ == '__main__':
    load_dotenv()

    log = logging.getLogger("agent")
    log.setLevel(logging.DEBUG)

    file_handler = logging.FileHandler('agent.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)

    log.addHandler(file_handler)
    log.addHandler(stdout_handler)

    engine = sqlalchemy.create_engine(os.environ['DATABASE_URL'], echo_pool=True, isolation_level='AUTOCOMMIT')
    current_modifiers = set()
    pending_hits = queue.Queue()

    def send_hits():
        while True:
            with engine.connect() as connection:
                hits = pending_hits.get()
                log.debug(f'sending: {hits}')
                connection.execute(TABLE.insert().values(hits=hits, ts=sqlalchemy.func.now()))

    threading.Thread(target=send_hits, daemon=True).start()

    def record_combos(keys):
        hits = '+'.join(keys)
        log.info(f'recoding: {hits}')
        pending_hits.put(hits)

    def on_press(key):
        if key in MODIFIERS:
            current_modifiers.add(key)
        else:
            record_combos(sorted([ str(key) for key in current_modifiers ]) + [ str(key) ])
        log.debug(f'{key} pressed, current_modifiers: {current_modifiers}')

    def on_release(key):
        if key in MODIFIERS:
            try:
                current_modifiers.remove(key)
            except KeyError:
                log.warn(f'Key {key} not in current_modifiers {current_modifiers}')
        log.debug(f'{key} released, current_modifiers: {current_modifiers}')

    with engine.connect() as connection:
        connection.execute(sqlalchemy.sql.text("""
            CREATE TABLE IF NOT EXISTS keyboard_monitor (
                hits STRING NULL,
                ts TIMESTAMP(3) NOT NULL,
                TIME INDEX ("ts")
            ) ENGINE=mito WITH( regions = 1, ttl = '3months')
        """))

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        try:
            log.info("Listening...")
            listener.join()
        except KeyboardInterrupt:
            log.info("Exiting...")
