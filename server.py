# Built-in modules
import sys, os, time, json, logging, socket, traceback
import numpy as np
from multiprocessing import Process, Queue
from queue import Empty as QueueEmpty
# Custom modules
from ModuleServer import utils, loggingProc, worker

help_text = \
'''_help can be called as "name" in the server hello for available modules. \
Likewise, _help can be called in request to workers as "function" fields \
(note it is still necessary to include other two fields eventhough they will be ignored).

_ping (or null) can be issued as well for "name" which will result in an echo of the client's IP.

Workers and server will send responses that are urlencoded(plus) json strings:
  {"response":RESPONSE,"error":ERROR_STATUS,"traceback":traceback.format_exc()}
     Where ERROR_STATUS is True/False and RESPONSE is from requested MODULE
All communication strings terminated by '\\n'


Client is expected to send urlencoded(plus) json strings with fields:
  Server hello:
  {"name":<name as str>}
     Server will send ack if successfully passed to worker queue
  Then the request for the worker:
  {
     "function":<function in "name" as str>,
     "args":[<arg0 as any type>,<arg1 as any type>,...],
     "keep_alive":<True/False>
  }
  Everything (including keep_alive) has 1 second timeout after server sends reply.
  Upon error in function, connection is closed regardless of keep_alive flag.
  Clients can also send a special request to nicely leave (e.g. no server timeout).
  {
     'function':None,
     'args':[],
     'keep_alive':False
  }'''

## CONFIG: see example config entry
##   If config specifies dispatch method, the first two args will always be 
##   the client IP then the function name. The remaining args are piped in from
##   client request as ordered args (e.g. *args)
##   If no dispatch method specified, function is called diretly with just *args
##

## General approach for procs:
## Logging is handled by separate process with one shared queue
## Main for loop will monitor:
##   - the config file
##       - If changed, will reload config file and modify workers only if needed
##       - Poorly configured entries are ignored
##       - Entry names beginning with '_' are ignored
##   - the spawned workers
##       - If worker unexpectedly dies, respawn with currently loaded config info
##       - If this process kills worker, or worker replies that it couldn't load the module,
##              then it is expected, and requires modifying the server config file
## Upon spawning:
##   - Each worker gets its own queue and the logging queue
##   - After spawning, a worker will reply True/False if successfully loaded the module (not the instance)
##   - If no response after a period of time, this main process will kill the worker
##       - The next time an attempt at spawning will be upon modification of config file
## Workers:
##   - They will handle the rest of the client request, and all communication to the client
##   - If the hardware module changes, they will reload the module and instance
##   - If None type received instead of client, signal to terminate
##   - _help is a special request that modules can overload in module namespace (not instance), but the
##       default will be a simple list of methods in the instance, or none if dispatcher is used
## Server aspect:
##   - Monitor for a connected client, perform first read to know which worker queue to put in
##   - Respond with ack
##   - Once in the worker queue and ack sent, the server is done, and worker is entirely responsible
##   - If queue full, appropriate error is sent to client trying to connect
##   - Server will pong a ping without sending to worker (immediately closing connection after)

LOGLEVEL = None
CONFIG_PATH = None
LOG_QUEUE = None
logger = None # setup in main()
modules = {} # {module_name:(config,(process_handle,queue))} (set in reload_config)

def clean_config(configFile):
    # Remove names beginning with underscore (e.g. comments/examples)
    [configFile.pop(name) for name in list(configFile) if name[0]=='_']
    configFile_changed = [False]*len(configFile)
    # Remove poorly formatted entries or duplicates
    for name in list(configFile): # Cant use iteritems because dynamically popping
        config = configFile[name]
        if type(config) != list:
            configFile.pop(name)
            logging.warning('Removing "%s" from config. The config value should be list'%name)
            continue
        if len(config) != 3:
            configFile.pop(name)
            logging.warning('Removing "%s" from config. The config value should have 3 entries (found %i)'%(name,len(config)))


def reload_config(modules,path):
    # Dictionary passed by pointer, so modify directly
    logging.info('Config file modified')
    try:
        with open(path,'rb') as fid:
            configFile = json.load(fid)
    except ValueError as err:
        raise ValueError('Failed to load config file (no modules changed): %s'%err.message)
    clean_config(configFile)
    loaded_workers = list(modules)
    for name,config in configFile.items():
        if name in loaded_workers: loaded_workers.remove(name)
        [old_config,old_props] = modules.get(name,[None]*2)
        if old_config != config or old_config is None:
            [proc,q] = load_module(name,config,old_props)
            modules[name] = (config,(proc,q))
    # Clean up any workers not found in new config file
    [_unload_module(name,modules[name][1]) for name in loaded_workers]
    [modules.pop(name) for name in loaded_workers]

def check_modules(modules):
    for name,props in modules.items():
        [config,[proc,q]] = props
        if proc and not proc.is_alive():
            logging.critical('%s died, relaunching'%name)
            modules[name] = (config,load_module(name,*props))

def _unload_module(name,old_module):
    # name: module name for logging
    # old_module: (process,queue) or None
    # Clean up old module if exists, preserve queue
    [proc,q] = old_module
    if proc:
        logging.info('Unloading %s'%name)
        q.put(None) # Signal to terminate
        logging.debug('Joining proc')
        try:
            proc.join(timeout=5)
        except:
            logger.error('Failed to join; terminating')
            proc.terminate()
        proc = None
    return (proc,q)

def load_module(name,config,old_module):
    # name: module name for logging
    # config: config used to reload
    # old_module: (process,queue) or None
    if old_module:
        [proc,q] = _unload_module(name,old_module)
    else:
        [proc,q] = [None,None]
    logger.info('Loading proc %s'%name)
    # Launch new process with queue (recycle if possible)
    # If fails to load in 10 seconds, give up
    if not q:
        logger.debug('Making new queue for %s'%name)
        q = Queue()
    proc = Process(target=worker.main,args=(name,config,q,LOG_QUEUE,LOGLEVEL),name=name)
    proc.start()
    # Check success of module load in worker
    try:
        success = q.get(timeout=5)
        if not success:
            proc = None
    except QueueEmpty:
        logger.error('Worker did not respond in timeout period, killing worker')
        proc.terminate()
        proc.join()
        proc = None
    return (proc,q)

def launchServer(addr,port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    server_address=(addr,port)
    sock.bind(server_address)
    logger.critical('starting up on %s port %s'%server_address)
    sock.listen(5)
    return sock

def handleClient(connection,addr):
    # Expects first transmission to be urlencoded json string
    # No finally block here, because upon getting on queue, dont close!
    try:
        msg = utils.recv(connection,validate_exists=['name'])
        if msg['name'] is None or msg['name'] == '_ping': # "ping request"
            utils.send(connection,addr)
            connection.close()
        elif msg['name'] == '_help':
            resp = 'Available modules: %s\n\n%s'%(', '.join(modules),help_text)
            utils.send(connection,resp)
            connection.close()
        else:
            if msg['name'] in modules:
                if modules[msg['name']][1][0].is_alive():
                    utils.send(connection,'ack')
                    modules[msg['name']][1][1].put((connection,addr))
                else:
                    raise Exception('%s worker is not alive!'%msg['name'])
            else:
                raise utils.BadRequest('%s does not exist (case matters)'%msg['name'])
    except:
        try:
            utils.send(connection,error=True)
        except:
            logger.exception('Could not send error to client')
        connection.close()
        logger.exception('Client %s handle failed'%addr[0])
    logger.debug('Finished handling client')

def main(server_name,config_path,server_addr='localhost',server_port=36577,loglevel=logging.DEBUG,logfile=None):
    global LOGLEVEL, LOG_QUEUE, CONFIG_PATH, logger
    LOGLEVEL = loglevel
    CONFIG_PATH = config_path
    os.system("title "+"%s (%s:%i)"%(server_name,server_addr,server_port))
    # Setup logging thread
    LOG_QUEUE = Queue()
    log_proc = Process(target=loggingProc.listener_process,args=(LOG_QUEUE,logfile),name='logging')
    log_proc.start()
    # Setup logging for main
    h = loggingProc.QueueHandler(LOG_QUEUE)
    logger = logging.getLogger()
    logger.addHandler(h)
    logger.setLevel(LOGLEVEL)
    sock = launchServer(server_addr,server_port)
    client_addr = (None,None)
    try:
        while True:
            try: # Main try block
                try:
                    connection, client_addr = sock.accept()
                    connection.setblocking(0)
                    logger.debug('New Client: %s'%(client_addr[0]))
                    handleClient(connection,client_addr)
                except IOError: # Most likely timeout error (every second)
                    # Check config file for changes
                    if utils.modified(CONFIG_PATH):
                        try:
                            reload_config(modules,CONFIG_PATH)
                        except:
                            logger.exception('Failed to reload config')
                    # Check to make sure workers are still running
                    check_modules(modules)
            except KeyboardInterrupt:
                raise
            except:
                logger.critical('Unhandled error in main loop (client: %s)'%client_addr[0],exc_info=True)
    except (KeyboardInterrupt,SystemExit):
        logger.critical('Shutting down')
    finally:
        sock.close() # No more connections
        try:
            for name,props in modules.items():
                _unload_module(name,props[1])
        finally:
            LOG_QUEUE.put_nowait(None)
            log_proc.join()

if __name__ == '__main__':
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(BASE_PATH,'server_test','server.config')
    logfile = os.path.join(BASE_PATH,'server_test','test_server.log')
    main('server_test',config_path,logfile=logfile)