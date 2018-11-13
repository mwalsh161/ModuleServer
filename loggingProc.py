import logging, traceback, sys, json
import logging.handlers

class LogJSONFormatter(logging.Formatter):
    # Note that the args field is always included if not empty!
    def __init__(self, include=['levelname','msg','created','exc_info','module']):
        self.include = include
        super(LogJSONFormatter, self).__init__()

    def format(self, record):
        data = {}
        if 'exc_info' in self.include:
            if record.exc_info:
                if record.exc_info[0]:
                    data['exc_info'] = {'type':record.exc_info[0].__name__,
                                        'msg':str(record.exc_info[1]),
                                        'stack':traceback.extract_tb(record.exc_info[2])}
                else:
                    data['exc_info'] = None
            else:
                data['exc_info'] = None
        if record.args:
            data['args'] = record.args
        for thing in self.include:
            if 'exc_info' != thing and 'message' != thing:
                data[thing] = getattr(record,thing)
        return json.dumps(data)

class QueueHandler(logging.Handler):
    """
    This is a logging handler which sends events to a multiprocessing queue.
    
    The plan is to add it to Python 3.2, but this can be copy pasted into
    user code for use with earlier Python versions.
    """

    def __init__(self, queue):
        """
        Initialise an instance, using the passed queue.
        """
        logging.Handler.__init__(self)
        self.queue = queue
        
    def emit(self, record):
        """
        Emit a record.

        Writes the LogRecord to the queue.
        """
        try:
            ei = record.exc_info
            if ei:
                dummy = self.format(record) # just to get traceback text into record.exc_text
                record.exc_info = None  # not needed any more
            self.queue.put_nowait(record)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

def listener_process(queue,filename=None):
    root = logging.getLogger()
    h = logging.StreamHandler(sys.stdout)
    f = logging.Formatter('%(asctime)s %(processName)-15s %(name)-8s %(levelname)-8s %(message)s')
    h.setFormatter(f)
    root.addHandler(h)
    if filename:
        h = logging.handlers.RotatingFileHandler(filename,maxBytes=10*1024*1024,backupCount=5)  # 10 MB
        f = LogJSONFormatter(['created','processName','name','levelname','msg','exc_info'])
        h.setFormatter(f)
        root.addHandler(h)
    while True:
        try:
            record = queue.get()
            if record is None: # We send this as a sentinel to tell the listener to quit.
                break
            logger = logging.getLogger(record.name)
            logger.handle(record) # No level or filter logic applied - just do it!
        except KeyboardInterrupt:
            pass
        except SystemExit:
            raise
        except:
            print('Whoops! Problem:')
            traceback.print_exc(file=sys.stderr)