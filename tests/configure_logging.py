"""Configure the loggers for the tests.
"""
import logging.config


class ListHandler(logging.Handler):
    """Collect LogRecords into a list.

    This class additionally calls ``.format()`` on the log-records in order to
    build the ``LogRecord.message`` attribute.
    """
    def __init__(self, level=logging.NOTSET):
        super(ListHandler, self).__init__(level)
        self.records = []

    def emit(self, record):
        try:
            # Discard the return value but use side effects
            self.format(record)
        except Exception:
            self.handleError(record)
        self.records.append(record)

    def flush(self):
        del self.records[:]


logging.config.dictConfig({
    'version': 1,
    'formatters': {
        'message': {
            'format': '%(message)s',
        },
    },
    'filters': {},
    'handlers': {
        'collector': {
            '()': ListHandler,
            'level': logging.DEBUG,
            'formatter': 'message',
        },
    },
    'root': {
        'level': logging.DEBUG,
        'handlers': ['collector']
    }
})


root_logger = logging.getLogger()

# This handler is the handler that captures all
# LogRecords sent to this module's logger
handler = root_logger.handlers[0]
""":type: tests.configure_logging.ListHandler"""
