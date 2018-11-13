import sys, os, traceback, time, logging, select
import urllib.parse as urllib
import importlib
import queue as Queue
from . import loggingProc, utils

# Currently can only handle 1 client
# Currently does not use __enter__ methods for INSTANCE instance, but does use __exit__

NAME = None  # Module name
CONFIG = None
PATH = None  # Path to module file to check modification
MODULE = None # module imported
# Instance of hardware class (None on first run; empty if errored)
# Purpose of setting to [] is to wait for change in file again
# before attempting to reload the module
INSTANCE = None
logger = None

class NoINSTANCE(Exception):
    pass

def handleClient(client):
    [client,addr] = client
    try:
        while True:
            msg = utils.recv(client,validate_exists=['keep_alive','function','args'])
            # Validate fields
            if msg['keep_alive'] not in [True,False]: raise utils.BadRequest('keep_alive must be a boolean')
            if type(msg['args']) is not list: raise utils.BadRequest('args should be a list of values')
            # Dispatch
            logger.debug('Dispatching: '+str(msg))
            if not INSTANCE: raise NoINSTANCE('Module failed to load INSTANCE') # handle case for []
            result = dispatch(client,addr,**msg)
            utils.send(client,result)
            if not msg['keep_alive']:
                break
    except IOError:
        logger.exception('Client lost')
    except:
        logger.exception('Error in client loop')
        utils.send(client,error=True)
    finally:
        logger.debug('Closed client: %s'%addr[0])
        client.close()

def dispatch(client,addr,function,args,**kwargs):
    # **kwargs is to allow direct kwarg passing of msg
    # Allow friendly disconnections
    if function is None:
        raise IOError('Client left gracefully') # IOError will not reply to client
    if CONFIG[2]:
        logger.debug('Using INSTANCE dispatcher.')
        result = getattr(INSTANCE,CONFIG[2])(addr[0],function,*args)
    else:
        if function not in dir(INSTANCE): raise utils.BadRequest('function not found in INSTANCE (case matters)')
        logger.debug('Using INSTANCE direct call.')
        result = getattr(INSTANCE,function)(*args)
    return result

def main(name,config,queue,log_queue,loglevel):
    global NAME, CONFIG, PATH, INSTANCE, MODULE, logger
    NAME = name
    CONFIG = config # [module path, entry point, dispatch fn/None]

    # Setup logging
    h = loggingProc.QueueHandler(log_queue)
    logger = logging.getLogger()
    logger.addHandler(h)
    logger.setLevel(loglevel)

    # Import this worker's MODULE (error here kills worker)
    try:
        logger.info('%s: Module loaded'%NAME)
        MODULE = importlib.import_module(CONFIG[0])
        assert MODULE, 'Module not found'
        PATH = os.path.abspath(MODULE.__file__) # .pyc file
        PATH = os.path.splitext(PATH)[0] + '.py'
        assert os.path.isfile(PATH), 'Could not find \'%s\''%CONFIG[0]
    except:
        logger.critical('Failed to load module',exc_info=True)
        queue.put(False)
        raise
    queue.put(True)

    # Begin main while loop
    try:
        while True:
            try: # Main try block
                try: # Queue block
                    msg = queue.get(timeout=1)
                    if msg is None:
                        logger.debug('%s worker returning'%NAME)
                        break
                    if INSTANCE is None: raise NoINSTANCE('INSTANCE does not exist yet')
                    handleClient(msg)
                except (Queue.Empty,NoINSTANCE):
                    # Effectively limit to on timeouts to not interfere
                    if utils.modified(PATH) or INSTANCE is None:
                        logger.debug('Reloading module and instance')
                        del(INSTANCE)
                        INSTANCE = [] # Used to signify error state in dispatch
                        importlib.reload(MODULE)
                        INSTANCE = getattr(MODULE,CONFIG[1])()

            except KeyboardInterrupt:
                pass
            except SystemExit:
                raise
            except:
                logger.exception('Unhandled error in main loop')
    finally:
        try:
            INSTANCE.__exit__(None,None,None)
            logger.debug('Exiting INSTANCE instance')
        except:
            logger.debug('INSTANCE instance has no __exit__')