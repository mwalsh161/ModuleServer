import socket, sys, logging, json
if sys.version_info[0] > 2:
    import urllib.parse as urllib
else:
    import urllib

# If you would like to use via commandline, it is recommended to run this
# file with the -i command: `python -i client.py`. This will setup basic
# logging.

logger = logging.getLogger(__name__)

DEFAULT_HOST = 'localhost'
DEFAULT_PORT = 36577
DEFAULT_TIMEOUT = 2

class client:
    """ Connect with server.py on host machine to control various pieces of equipment
       
        Attributes
        ----------
        host : str
            Hostname or IP of server.
        port : int
            Port number on `host`.
        timeout : int, float
            Time in seconds to wait for server to reply. Same as socket.timeout.

        Notes
        -----
        Some ModuleServer operations could conceivably take longer than the default timeout used here.
    """

    def __init__(self,host=DEFAULT_HOST,port=DEFAULT_PORT,timeout=DEFAULT_TIMEOUT):
        self.host = host
        self.port = port
        self.timeout = timeout
        logger.debug('Client instance created at %s port %s.' % (host, port))

    def __connect_socket(self):
        # Create a TCP/IP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)

        # Connect the socket to the port where the server is listening
        server_address = (self.host, self.port)
        logger.debug('connecting to %s port %s' % server_address)
        sock.connect(server_address)

        return sock

    def __close_socket(self,sock):
        logger.debug('closing socket')
        sock.close()

    def __recv(self,sock,delim='\n',recv_buffer=4096):
        buffer = ''
        while True:
            data = urllib.unquote_plus(sock.recv(recv_buffer).decode())
            assert data, 'Srver disconnected while receiving.'
            buffer += data
            if data[-1] == delim:
                msg = json.loads(buffer[0:-len(delim)])  # Remove delims
                if msg['error']:
                    raise Exception('Server Error: '+msg['response']+\
                        '\n|'+msg['traceback'].strip().replace('\n','\n|'))
                else:
                    return msg['response']
    
    def __send_and_recv(self,sock,message,close_after=True):
        # Server always replies and always closes connection after msg
        resp = None

        try:
            # Send message
            logger.debug('sending "%s"' % message)
            sock.sendall((urllib.quote_plus(message)+'\n').encode())

            # Look for the response
            resp = self.__recv(sock)
            logger.debug('received "%s"' % resp)
            
        finally:
            if close_after:
                self.__close_socket(sock)
        return resp

    def com(self,module,funcname='_help',*args):
        """ Default communication method
            
            Parameters
            ----------
            module : str
                Name of ModuleServer's module you are attempting to talk to.
                A list of names can be retrieved using `self.get_modules()`.
            funcname : str
                The name of the function within `module`. You can retrieve the module's
                help text by using the default value of funcname, '_help': `self.com('moduleA')`.
            *args : json-serializable, optional
                The input values required by the `module`'s `funcname` method.
        """
        # keep_alive not supported by client
        
        # Prepare both parts of message in case one errors
        handshake = json.dumps({"name":module})
        message = json.dumps({"function":funcname,
            "args":args,
            "keep_alive":False})

        sock = self.__connect_socket()

        # Send handshake, look for response and check if ack is received
        resp = self.__send_and_recv(sock,handshake,False)
        assert resp == 'ack', (
            'Wasn\'t able to get an acknowledgement from the server')

        # Send message and return response
        return self.__send_and_recv(sock,message)

    def help(self):
        """ Retrieve help text from the server
        """
        sock = self.__connect_socket()
        message = json.dumps({"name":"_help"})

        return self.__send_and_recv(sock,message)

    def ping(self):
        """ Server responds with ('IP',port) of connected socket
        """
        sock = self.__connect_socket()
        message = json.dumps({"name":"_ping"})

        return self.__send_and_recv(sock,message)

    def reload(self,module):
        """ Force server to reload `module`
            
            Parameters
            ----------
            module : str
                Name of ModuleServer's module you are attempting to talk to.
                A list of names can be retrieved using `self.get_modules()`.
        """
        sock = self.__connect_socket()
        assert isinstance(module,str), 'module must be a string'
        message = json.dumps({"name":"_reload_"+module})
        resp = self.__send_and_recv(sock,message)
        # Elevate server failed response to error
        if resp == 'Failed to find module "%s"'%module:
            raise Exception('Server Error: ' + resp)

        return resp

    def get_modules(self,prefix=''):
        """ Get available modules from server.
            
            Parameters
            ----------
            prefix : str, optional
                Filter modules retrieved from server based on a common prefix to their name.
        """
        sock = self.__connect_socket()
        assert isinstance(prefix,str), 'prefix must be a string'
        message = json.dumps({"name":"_get_modules."+prefix})

        return self.__send_and_recv(sock,message)

if __name__ == '__main__':
    import logging.handlers
    h = logging.handlers.RotatingFileHandler('client.log',maxBytes=10*1024*1024,backupCount=5)  # 10 MB
    f = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    h.setFormatter(f)
    logger.addHandler(h)
    logger.setLevel(logging.DEBUG)
