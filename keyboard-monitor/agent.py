from dotenv import load_dotenv
from pynput import keyboard
from pynput.keyboard import Key

import concurrent.futures
import logging
import os
import queue
import sqlalchemy
import sqlalchemy.exc
import sys
import time


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
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(funcName)s %(message)s')
    file_handler = logging.FileHandler(f'agent-{time.time_ns()}.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.setFormatter(formatter)
    log.addHandler(file_handler)
    log.addHandler(stdout_handler)

    engine = sqlalchemy.create_engine(os.environ['DATABASE_URL'], echo_pool=True, isolation_level='AUTOCOMMIT')
    current_modifiers = set()
    pending_hits = queue.Queue()
    cancel_signal = queue.Queue()

    def on_press(key):
        if key in MODIFIERS:
            current_modifiers.add(key)
        else:
            hits = sorted([ str(key) for key in current_modifiers ]) + [ str(key) ]
            hits = '+'.join(hits)
            pending_hits.put(hits)
        log.debug(f'{key} pressed, current_modifiers: {current_modifiers}')

    def on_release(key):
        if key in MODIFIERS:
            try:
                current_modifiers.remove(key)
            except KeyError:
                log.warning(f'Key {key} not in current_modifiers {current_modifiers}')
        log.debug(f'{key} released, current_modifiers: {current_modifiers}')

    with engine.connect() as connection:
        connection.execute(sqlalchemy.sql.text("""
            CREATE TABLE IF NOT EXISTS keyboard_monitor (
                hits STRING NULL,
                ts TIMESTAMP(3) NOT NULL,
                TIME INDEX ("ts")
            ) ENGINE=mito WITH( ttl = '3months')
        """))

    def sender_thread():
        retries = 0
        while True:
            hits = pending_hits.get()
            log.debug(f'got: {hits}')
            if hits is None:
                log.info("Exiting...")
                break
            with engine.connect() as connection:
                try:
                    log.debug(f'sending: {hits}')
                    connection.execute(TABLE.insert().values(hits=hits, ts=sqlalchemy.func.now()))
                    log.info(f'sent: {hits}')
                    retries = 0
                except sqlalchemy.exc.OperationalError as e:
                    if retries >= 10:
                        log.error(f'Retry exceeds. Operational error: {e}')
                        pending_hits.put(hits)
                        continue

                    if e.connection_invalidated:
                        log.warning(f'Connection invalidated: {e}')
                        pending_hits.put(hits)
                        continue

                    msg = str(e)
                    if "(1815, 'Internal error: 1000')" in msg:
                        # TODO 1815 - should not handle internal error;
                        # see https://github.com/GreptimeTeam/greptimedb/issues/3447
                        log.warning(f'Known operational error: {e}')
                        pending_hits.put(hits)
                        continue
                    elif '2005' in msg and 'Unknown MySQL server host' in msg:
                        log.warning(f'DNS temporary unresolved: {e}')
                        pending_hits.put(hits)
                        continue

                    raise e
                finally:
                    retries += 1

    def listener_thread():
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            log.info("Listening...")
            cancel_signal.get()
            pending_hits.put(None)
            log.info("Exiting...")

    with concurrent.futures.ThreadPoolExecutor() as executor:
        sender = executor.submit(sender_thread)
        listener = executor.submit(listener_thread)
        try:
            f = concurrent.futures.wait([sender, listener], return_when=concurrent.futures.FIRST_EXCEPTION)
            for fut in f.done:
                log.error(f'Unhandled exception for futures: {fut.exception(timeout=0)}')
        except KeyboardInterrupt as e:
            log.info("KeyboardInterrupt. Exiting...")
        except Exception as e:
            log.error(f'Unhandled exception: {e}')
        finally:
            cancel_signal.put(True)
