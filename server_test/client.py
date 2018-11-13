import sys, os, socket, time
import urllib, json
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(BASE_PATH,'..'))
import utils

def recv(sock):
    msg = utils.recv(sock)
    if msg['error']:
        raise Exception('Server Error: '+msg['response']+'\n'+msg['traceback'])
    else:
        return msg['response']

print 'mod'
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = ('localhost', 36577)
    sock.connect(server_address)
    sock.settimeout(1)
    msg = {'name':'mod'}
    sock.sendall(urllib.quote_plus(json.dumps(msg))+'\n')
    ack = recv(sock)
    
    msg = {
           'function':'my_fun',
           'args':['ay',1,False,None],
           'keep_alive':False
          }
    sock.sendall(urllib.quote_plus(json.dumps(msg))+'\n')
    resp = recv(sock)
    print resp

finally:
    print 'Closing socket'
    sock.close()

print 'mod2'
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = ('localhost', 36577)
    sock.connect(server_address)
    sock.settimeout(1)
    msg = {'name':'mod2'}
    sock.sendall(urllib.quote_plus(json.dumps(msg))+'\n')
    ack = recv(sock)
    
    msg = {
           'function':'my_fun',
           'args':['ay',1,False,None],
           'keep_alive':True
          }
    sock.sendall(urllib.quote_plus(json.dumps(msg))+'\n')
    resp = recv(sock)
    print resp

finally:
    print 'Closing socket'
    msg = {
            'function':None,
            'args':[],
            'keep_alive':True
           }
    sock.sendall(urllib.quote_plus(json.dumps(msg))+'\n')
    sock.close()