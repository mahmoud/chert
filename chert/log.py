# -*- coding: utf-8 -*-

import os

from lithoxyl import Logger, SensibleSink, Formatter, StreamEmitter
from lithoxyl.filters import ThresholdFilter

chert_log = Logger('chert')
# TODO: duration_s, duration_ms, duration_us
stderr_fmt = Formatter('{status_char}{end_local_iso8601_noms_notz} - {duration_msecs}ms - {message}')
stderr_emt = StreamEmitter('stderr')
stderr_filter = ThresholdFilter(success='info',
                                failure='debug',
                                exception='debug')
stderr_sink = SensibleSink(formatter=stderr_fmt,
                           emitter=stderr_emt,
                           filters=[stderr_filter])
chert_log.add_sink(stderr_sink)


# Lithoxyl TODO: Sink which emits an extra record if a certain amount
# of time has passed.

class DevDebugSink(object):
    # TODO: configurable max number of traceback signatures, after
    #       which exit/ignore?

    def __init__(self, reraise=False, post_mortem=False):
        self.reraise = reraise
        self.post_mortem = post_mortem

    #def on_complete(self, record):
    #    if record.name == 'entry load':
    #        import pdb;pdb.set_trace()

    def on_exception(self, record, exc_type, exc_obj, exc_tb):
        if self.post_mortem:
            import pdb; pdb.post_mortem()
        if self.reraise:
            raise exc_type, exc_obj, exc_tb


chert_log.add_sink(DevDebugSink(post_mortem=os.getenv('CHERT_PDB')))


def _ppath(path):  # lithoxyl todo
    # find module path (or package path) and relativize to that?
    if not path.startswith('/'):
        return path
    rel_path = os.path.relpath(path, input_path)
    if rel_path.startswith('..'):
        return path
    return rel_path


def rec_dec(record, inject_as=None, **rec_kwargs):
    if inject_as and not isinstance(inject_as, str):
        raise TypeError('inject_as expected string, not: %r' % inject_as)

    def func_wrapper(func):
        def logged_func(*a, **kw):
            # kwargs: reraise + extras. message/raw_message/etc?
            # rewrite Callpoint of record to be the actual wrapped function?
            logger = record.logger
            new_record = logger.record(record.name, record.level, **rec_kwargs)
            if inject_as:
                kw[inject_as] = new_record
            with new_record:
                return func(*a, **kw)
        return logged_func
    return func_wrapper
