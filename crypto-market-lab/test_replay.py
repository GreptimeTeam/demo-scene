"""Protect playback boundaries, same-timestamp steps, and pause consistency."""
import threading
import time
import unittest
from unittest.mock import patch

from replay import Replay


class MemoryDatabase:
    def __init__(self):
        self.session = self
        self.written = []
        self.batch_entered = threading.Event()
        self.release_write = threading.Event()
        self.release_write.set()

    def rows(self, statement):
        return [[11, '100', '1', 1_000_000, True],
                [12, '101', '2', 1_000_000, False],
                [13, '102', '3', 5_000_000, True]]

    def write(self, batch, *args):
        self.batch_entered.set()
        if not self.release_write.wait(2):
            raise AssertionError('Test write did not resume')
        self.written.extend(batch)

    def sql(self, statement):
        pass

    def status(self, *args, **kwargs):
        pass

    def close(self):
        pass


class ReplayTest(unittest.TestCase):
    def wait(self, replay, predicate):
        deadline = time.monotonic()+3
        while time.monotonic() < deadline:
            state = replay.snapshot()
            if predicate(state):
                return state
            if state['status'] == 'failed':
                self.fail(state)
            time.sleep(.005)
        self.fail(replay.snapshot())

    def test_single_trade_steps_and_resume_without_duplicates(self):
        db = MemoryDatabase()
        with patch('replay.Database', return_value=db):
            replay = Replay()
            replay.start('BTCUSDT', 1_000_000, 1, 1, paused=True)
            self.wait(replay, lambda s: s['status'] == 'paused')
            self.assertEqual(db.written, [])
            replay.control('step')
            state = self.wait(replay, lambda s: s['written'] == 1)
            self.assertEqual((state['cursor'],state['last_trade_id']), (1_000_000,11))
            self.assertEqual(state['status'], 'paused')
            replay.control('step')
            state = self.wait(replay, lambda s: s['written'] == 2)
            self.assertEqual(state['last_trade_id'],12)
            replay.control('speed',100)
            replay.control('play')
            self.wait(replay, lambda s: s['status'] == 'complete')
            self.assertEqual([t.trade_id for t in db.written],[11,12,13])

    def test_pause_acknowledges_committed_write_and_stop_wakes_paused_worker(self):
        db = MemoryDatabase()
        db.release_write.clear()
        with patch('replay.Database', return_value=db):
            replay = Replay()
            replay.start('BTCUSDT', 1_000_000, 1, 1)
            self.assertTrue(db.batch_entered.wait(2))
            acknowledged = threading.Event()
            def pause():
                replay.control('pause')
                acknowledged.set()
            thread = threading.Thread(target=pause)
            thread.start()
            self.assertFalse(acknowledged.wait(.03))
            db.release_write.set()
            self.assertTrue(acknowledged.wait(2))
            thread.join()
            before = replay.snapshot()['written']
            time.sleep(.03)
            self.assertEqual(replay.snapshot()['written'],before)
            replay.stop()
            state = self.wait(replay, lambda s: s['status'] == 'stopped')
            self.assertEqual(state['written'],before)
            self.assertLess(before,3)


if __name__ == '__main__':
    unittest.main()
