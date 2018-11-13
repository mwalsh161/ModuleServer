import os, logging
logger = logging.getLogger(__name__)

class foo2:
    def __init__(self):
        pass

    def my_fun(self,*args):
        logger.debug('You did it: %s'%str(args))
        return 'hooray'