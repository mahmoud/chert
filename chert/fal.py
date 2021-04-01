"""
File Access Layer
"""
try:
    unicode
except NameError:
    unicode = str

class ChertFAL(object):
    def __init__(self, logger):
        # relative path for pprinting
        self.logger = logger

    def read(self, path, level='debug'):
        level_method = getattr(self.logger, level)
        with level_method('read file {path}', path=path) as rec:
            with open(path, 'rb') as f:
                ret = f.read()
            rec.success('read {data_len} bytes from {path}', data_len=len(ret))
        return ret

    def write(self, path, data, level='debug', encoding='utf-8'):
        level_method = getattr(self.logger, level)
        with level_method('write file {path}', path=path) as rec:
            if isinstance(data, unicode):
                output_bytes = data.encode(encoding)
            else:
                output_bytes = data
            with open(path, 'wb') as f:
                f.write(output_bytes)
            rec.success('wrote {data_len} bytes to {path}',
                        data_len=len(output_bytes))
        return
