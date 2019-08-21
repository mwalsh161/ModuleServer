import os, logging, time
logger = logging.getLogger(__name__)

class foo:
    def __init__(self):
   #     raise Exception('Boooo')
        logger.debug('Here we go')
        time.sleep(3)
        logger.debug('Finally')

    def dispatch(self,client_ip,fn_name,*args):
        logger.debug('Calling '+fn_name+str(args))
        return 'hi!',True