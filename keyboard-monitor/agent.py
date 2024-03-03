from dotenv import load_dotenv
from pynput import keyboard
from pynput.keyboard import Key
import os
import sqlalchemy


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

    engine = sqlalchemy.create_engine(os.environ['DATABASE_URL'], echo_pool=True, isolation_level='AUTOCOMMIT')
    current_modifiers = set()

    def record_combos(keys):
        hits = '+'.join(keys); print(hits)
        with engine.connect() as connection:
            connection.execute(sqlalchemy.insert(TABLE).values(hits=hits, ts=sqlalchemy.func.now()))

    def on_press(key):
        if key in MODIFIERS:
            current_modifiers.add(key)
        else:
            record_combos(sorted([ str(key) for key in current_modifiers ]) + [ str(key) ])

    def on_release(key):
        if key in MODIFIERS:
            try:
                current_modifiers.remove(key)
            except KeyError:
                print(f'Key {key} not in current_modifiers {current_modifiers}')

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
            listener.join()
        except KeyboardInterrupt:
            print("Exiting...")
