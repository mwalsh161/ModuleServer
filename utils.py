import os, time, json, sys, traceback, socket
if sys.version_info[0] > 2:
    import urllib.parse as urllib
else:
    import urllib

class timeout(IOError):
    pass
class BadRequest(Exception):
    pass

def modified(path):
    # Check modification from mtime and hash of contents
    # First call will return True
    changed = False
    mtime = os.path.getmtime(path)
    try:
        check_config = modified.last[path]
    except:
        check_config = (None,None)
    if mtime != check_config[0]:
        time.sleep(0.1) # Allow OS to finish writing
        with open(path,'rb') as fid:
            f_hash = hash(fid.read())
        if f_hash != check_config[1]:
            changed = True
        modified.last[path] = (mtime,f_hash)
    return changed
modified.last = {} # Initialize

def recv(connection,delim=b'\n',recv_buffer=4096,time_out=1,validate_exists=[]):
    buffer = b''
    tstart = time.time()
    while time.time() - tstart < time_out:
        try:
            data = connection.recv(recv_buffer)
        except socket.timeout:
            raise
        except IOError as err:
            if err.errno in [35, 10035]: # Resource temporarily unavailable, Timeout
                time.sleep(0.01)
                continue
            raise
        if not data: raise IOError('Client disconnected while receiving.')
        buffer += data
        if data[-1:] == delim:
            msg = buffer[0:-len(delim)].decode('utf-8')  # Remove delim
            try:
                msg = urllib.unquote_plus(msg)
                msg = json.loads(msg)
            except Exception as err:
                raise Exception('Failed to decode msg: "%s"'%(msg,))
            for field in validate_exists:
                if field not in msg: raise BadRequest('"%s" field missing from request.'%field)
            return msg
    raise timeout('Did not receive all client data in timeout period (%g seconds). Make sure terminated with "\\n".\nPartial message: "%s"'% \
        (time_out,urllib.unquote_plus(buffer.decode('utf-8'))))

def send(connection,resp='',delim=b'\n',error=False):
    # error -> either True/False or an Exception object
    tb_formatted = ''
    if error: # Anything but empty, 0, or False
        if error is True:  # Use current exception to print traceback
            exc = sys.exc_info()[1] # exc_info returns (type,exc,traceback)
        else:              # error is some Exception object, so use that
            exc = error
        tb_formatted = ''.join(traceback.format_exception(None,exc,exc.__traceback__))
    resp = json.dumps({'response':resp,'error':bool(error),'traceback':tb_formatted})
    connection.sendall(bytes(urllib.quote_plus(resp),'utf-8')+delim)