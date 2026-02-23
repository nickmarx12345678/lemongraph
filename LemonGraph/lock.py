import logging
import os
import fcntl
import time

log = logging.getLogger(__name__)

class Lock(object):
    _close = os.close

    # byte-range file locking is tracked by process for an inode.
    # when a process closes a file descriptor, any locks it had
    # on the underlying inode are released.
    # therefore, only open a given lock file once within a process.
    def __init__(self, lockfile):
        self.fd = self.ctx = None
        self.fd = os.open(lockfile, os.O_RDWR | os.O_CREAT)

    def context(self, *keys, **kwargs):
        if not keys:
            raise RuntimeError('missing required keys!')
        elif self.ctx is not None:
            raise RuntimeError('only one active context allowed!')

        kwargs['_ctx_cleanup'] = self._ctx_cleanup
        self.ctx = Ctx(self.fd, keys, **kwargs)
        return self.ctx

    def lock(self, *keys, **kwargs):
        if 'lock' not in kwargs:
            kwargs['lock'] = True
        return self.context(*keys, **kwargs)

    def shared(self, *keys, **kwargs):
        kwargs['excl'] = False
        return self.lock(*keys, **kwargs)

    def exclusive(self, *keys, **kwargs):
        kwargs['excl'] = True
        return self.lock(*keys, **kwargs)


    def _ctx_cleanup(self):
        self.ctx = None

    def close(self):
        if self.fd is not None:
            self._close(self.fd)
            self.fd = None

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


class Ctx(object):
    def __init__(self, fd, keys, excl=True, lock=False, mod=1048573, _ctx_cleanup=None):
        self.fd = fd
        self.locked = False
        self.mode = fcntl.LOCK_EX if excl else fcntl.LOCK_SH
        self._ctx_cleanup = _ctx_cleanup

        # sort so locks are acquired in consistent order
        # guarantees no inter-process deadlocks
        locks = set(hash(key) % mod for key in keys)
        self.locks = tuple(sorted(locks))

        if lock:
            self.lock()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self._update(None)
        if self._ctx_cleanup is not None:
            self._ctx_cleanup()

    def _update(self, mode):
        if mode is None:
            if self.locked:
                log.debug('lock: releasing offsets=%s pid=%d', self.locks, os.getpid())
                fcntl.lockf(self.fd, fcntl.LOCK_UN)
                self.locked = False
        elif self.mode is not mode or not self.locked:
            self.mode = mode
            kind = 'exclusive' if mode == fcntl.LOCK_EX else 'shared'
            log.info('lock: acquiring %s offsets=%s pid=%d', kind, self.locks, os.getpid())
            t0 = time.monotonic()
            self.locked = True
            for offset in self.locks:
                fcntl.lockf(self.fd, self.mode, 1, offset)
            elapsed = time.monotonic() - t0
            if elapsed > 0.1:
                log.warning('lock: acquired %s offsets=%s pid=%d took %.3fs', kind, self.locks, os.getpid(), elapsed)
            else:
                log.info('lock: acquired %s offsets=%s pid=%d took %.3fs', kind, self.locks, os.getpid(), elapsed)

    def shared(self):
        self._update(fcntl.LOCK_SH)

    def exclusive(self, *keys):
        self._update(fcntl.LOCK_EX)

    def unlock(self):
        self._update(None)

    def lock(self):
        self._update(self.mode)
