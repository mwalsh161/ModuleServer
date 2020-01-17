import socket, sys, logging, urllib.parse, json

logging.basicConfig(filename='client_log.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)
logger = logging.getLogger(__name__)

class client:
    # CLIENT connects with server.py on host machine to control
    #  varoius pieces of equipment
    #  Note, some hwserver operations could conveivably take longer than the
    #  default timeout used here. If so, obj.connection.Timeout should be
    #  adjusted appropriately

    DEFAULT_HOST = 'localhost'
    DEFAULT_PORT = 36577
    DEFAULT_TIMEOUT = 2

    def __init__(self,host=DEFAULT_HOST,port=DEFAULT_PORT):
        self.host = host
        self.port = port
        self.timeout = self.DEFAULT_TIMEOUT
        server_address = (host, port)
        logger.debug('Client instance created at %s port %s.' % server_address)

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
            data = urllib.parse.unquote_plus(sock.recv(recv_buffer).decode())
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
        resp = None

        try:
            # Send message
            logger.debug('sending "%s"' % message)
            sock.sendall((urllib.parse.quote_plus(message)+'\n').encode())

            # Look for the response
            resp = self.__recv(sock)
            logger.debug('received "%s"' % resp)
            
        finally:
            if close_after:
                self.__close_socket(sock)
        return resp

    def com(self,module,funcname,*args):
        # Server always replies and always closes connection after msg
        # assert funcname is a string, and cast varargin (cell array)
        # to strings (use cellfun - operates on each entry of cell)
        
        # last input is the keep_alive; for now, functionality not
        # included
        assert isinstance(module,str), 'module must be a string'
        assert isinstance(funcname,str), 'funcname must be a string'
        
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
        sock = self.__connect_socket()
        message = json.dumps({"name":"_help"})

        return self.__send_and_recv(sock,message)

    def ping(self):
        sock = self.__connect_socket()
        message = json.dumps({"name":"_ping"})

        return self.__send_and_recv(sock,message)

    def reload(self,module):
        sock = self.__connect_socket()
        assert isinstance(module,str), 'module must be a string'
        message = json.dumps({"name":"_reload_"+module})

        return self.__send_and_recv(sock,message)

    def get_modules(self,prefix=''):
        sock = self.__connect_socket()
        assert isinstance(prefix,str), 'prefix must be a string'
        message = json.dumps({"name":"_get_modules."+prefix})

        return self.__send_and_recv(sock,message)