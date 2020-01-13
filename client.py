import socket, sys, logging, urllib.parse, json

logging.basicConfig(filename='client_log.log',
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG)
logger = logging.getLogger(__name__)

class client:

    DEFAULT_IP = 'localhost'
    DEFAULT_PORT = 36577

    def __init__(self,ip=DEFAULT_IP,port=DEFAULT_PORT):
        self.ip = ip
        self.port = port
        server_address = (ip, port)
        logger.debug('Client instance created with IP %s port %s.' % server_address)

    def __connect_socket(self):
        # Create a TCP/IP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)

        # Connect the socket to the port where the server is listening
        server_address = (self.ip, self.port)
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
                    raise Exception('Server Error: '+msg['response']+'\n'+msg['traceback'])
                else:
                    return msg['response']

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

        resp = None

        try:
            # Send handshake
            logger.debug('sending "%s"' % handshake)
            sock.sendall((urllib.parse.quote_plus(handshake)+'\n').encode())

            # Look for the response and check if module exists
            resp = self.__recv(sock)
            logger.debug('received "%s"' % resp.strip())
            assert resp == 'ack', '%s does not exist' % module
            
            # Send data
            logger.debug('sending "%s"' % message)
            sock.sendall((urllib.parse.quote_plus(message)+'\n').encode())

            # Look for the response
            resp = self.__recv(sock)
            logger.debug('received "%s"' % resp.strip())

        finally:
            self.__close_socket(sock)
        return resp

    def help(self):
        handshake = json.dumps({"name":"_help"})

        sock = self.__connect_socket()

        resp = None

        try:
            # Send handshake
            logger.debug('sending "%s"' % handshake)
            sock.sendall((urllib.parse.quote_plus(handshake)+'\n').encode())

            # Look for the response
            resp = self.__recv(sock)
            logger.debug('received "%s"' % resp.strip())

        finally:
            self.__close_socket(sock)
        return resp

    def ping(self):
        handshake = json.dumps({"name":"_ping"})

        sock = self.__connect_socket()

        resp = None

        try:
            # Send handshake
            logger.debug('sending "%s"' % handshake)
            sock.sendall((urllib.parse.quote_plus(handshake)+'\n').encode())

            # Look for the response
            resp = self.__recv(sock)
            logger.debug('received ["%s",%s]' % (resp[0], resp[1]))

        finally:
            self.__close_socket(sock)
        return resp

    def reload(self,module):
        assert isinstance(module,str), 'module must be a string'

        handshake = json.dumps({"name":"_reload_"+module})

        sock = self.__connect_socket()

        resp = None

        try:
            # Send handshake
            logger.debug('sending "%s"' % handshake)
            sock.sendall((urllib.parse.quote_plus(handshake)+'\n').encode())

            # Look for the response
            resp = self.__recv(sock)
            logger.debug('received "%s"' % resp.strip())

        finally:
            self.__close_socket(sock)
        return resp




