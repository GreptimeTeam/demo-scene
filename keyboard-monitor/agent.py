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


class KeyboardMonitor:
    def __init__(self) -> None:
        load_dotenv()
        self.current_modifiers = set()
        self.engine = sqlalchemy.create_engine(os.environ['DATABASE_URL'])
        self.connection = self.engine.connect()
        self.listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)


    def __enter__(self):
        self.listener.__enter__()
        return self
    

    def __exit__(self, exc_type, exc_value, traceback):
        self.listener.__exit__(exc_type, exc_value, traceback)


    def on_press(self, key):
        if key in MODIFIERS:
            self.current_modifiers.add(key)
        else:
            self.record_combos(sorted([ str(key) for key in self.current_modifiers ]) + [ str(key) ])


    def on_release(self, key):
        if key in MODIFIERS:
            try:
                self.current_modifiers.remove(key)
            except KeyError:
                print(f'Key {key} not in current_modifiers {self.current_modifiers}')


    def record_combos(self, keys):
        hits = '+'.join(keys)
        print(hits)
        self.connection.execute(sqlalchemy.insert(TABLE).values(hits=hits, ts=sqlalchemy.func.now()))
        self.connection.commit()


if __name__ == '__main__':
    with KeyboardMonitor() as monitor:
        monitor.connection.execute(sqlalchemy.sql.text("""
            CREATE TABLE IF NOT EXISTS keyboard_monitor (
                hits STRING NULL,
                ts TIMESTAMP(3) NOT NULL,
                TIME INDEX ("ts")
            ) ENGINE=mito WITH( regions = 1, ttl = '3months')
        """))
        monitor.connection.commit()

        try:
            monitor.listener.join()
        except KeyboardInterrupt:
            print("Exiting...")
            pass
