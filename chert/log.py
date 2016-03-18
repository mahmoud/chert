# -*- coding: utf-8 -*-

import os

from lithoxyl import (Logger,
                      StreamEmitter,
                      SensibleSink,
                      SensibleFormatter)

from lithoxyl.filters import ThresholdFilter
from lithoxyl.sinks import DevDebugSink


chert_log = Logger('chert')
# TODO: duration_s, duration_ms, duration_us
' - {duration_ms:>8.3f}ms'
fmt = ('{status_char}+{import_delta_s}'
       ' - {duration_auto}'
       ' - {parent_depth_indent}{end_message}')

stderr_fmtr = SensibleFormatter(fmt)
stderr_emtr = StreamEmitter('stderr')
stderr_filter = ThresholdFilter(success='info',
                                failure='debug',
                                exception='debug')
stderr_sink = SensibleSink(formatter=stderr_fmtr,
                           emitter=stderr_emtr,
                           filters=[stderr_filter])
chert_log.add_sink(stderr_sink)

try:
    from lithoxyl.emitters import SyslogEmitter
except Exception:
    pass
else:
    syslog_filter = ThresholdFilter(success='critical',
                                    failure='critical',
                                    exception='critical')
    syslog_emt = SyslogEmitter('chert')
    syslog_sink = SensibleSink(formatter=stderr_fmtr,
                               emitter=syslog_emt,
                               filters=[syslog_filter])
    if os.getenv('CHERT_SYSLOG'):
        chert_log.add_sink(syslog_sink)


chert_log.add_sink(DevDebugSink(post_mortem=os.getenv('CHERT_PDB')))


def _ppath(path):  # lithoxyl todo
    # find module path (or package path) and relativize to that?
    if not path.startswith('/'):
        return path
    rel_path = os.path.relpath(path, input_path)
    if rel_path.startswith('..'):
        return path
    return rel_path
