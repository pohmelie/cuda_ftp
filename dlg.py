import os
from cudatext import *

is_unix = os.name!='nt'

def dialog_server_props(s_type, s_host, s_port,
                        s_username, s_password, s_dir, s_timeout,
                        s_label, s_uselist):

    RES_TYPE_FTP = 1
    RES_TYPE_SFTP = 2
    RES_HOST = 4
    RES_PORT = 6
    RES_USERNAME = 8
    RES_PASS = 10
    RES_PASS_DEFAULT = 11
    RES_PASS_ASK = 12
    RES_DIR = 14
    RES_TIMEOUT = 16
    RES_LABEL = 18
    RES_USELIST = 19
    RES_OK = 20

    c1 = chr(1)
    while True:
        res = dlg_custom('FTP server info', 496, 360,
          '\n'.join([]
             +[c1.join(['type=label', 'pos=6,8,190,0', 'cap=Server type:'])]
             +[c1.join(['type=radio', 'pos=180,6,250,0', 'cap=FTP', 'val='+('1' if s_type=='ftp' else '0') ])]
             +[c1.join(['type=radio', 'pos=250,6,350,0', 'cap=SFTP', 'val='+('1' if s_type=='sftp' else '0'), 'en='+('1' if is_unix else '0') ])]

             +[c1.join(['type=label', 'pos=6,38,148,0', 'cap=Host (e.g. ftp.site.com):'])]
             +[c1.join(['type=edit', 'pos=180,36,490,0', 'val='+s_host])]

             +[c1.join(['type=label', 'pos=6,68,148,0', 'cap=Port:'])]
             +[c1.join(['type=edit', 'pos=180,66,240,0', 'val='+s_port])]

             +[c1.join(['type=label', 'pos=6,98,148,0', 'cap=Username:'])]
             +[c1.join(['type=edit', 'pos=180,96,490,0', 'val='+s_username])]

             +[c1.join(['type=label', 'pos=6,128,148,0', 'cap=Password:'])]
             +[c1.join(['type=edit_pwd', 'pos=180,126,490,0', 'val='+(s_password if s_password!='?' else '') ])]
             +[c1.join(['type=button', 'pos=180,156,380,0', 'cap=Default anonymous login' ])]
             +[c1.join(['type=check', 'pos=180,186,490,0', 'cap=Ask password every time', 'val='+('1' if s_password=='?' else '0') ])]

             +[c1.join(['type=label', 'pos=6,218,148,0', 'cap=Initial remote dir:'])]
             +[c1.join(['type=edit', 'pos=180,216,490,0', 'val='+s_dir])]

             +[c1.join(['type=label', 'pos=6,248,148,0', 'cap=Timeout (seconds):'])]
             +[c1.join(['type=spinedit', 'pos=180,246,240,0', 'props=1,120,1', 'val='+s_timeout])]

             +[c1.join(['type=label', 'pos=6,278,148,0', 'cap=Label (for menu):'])]
             +[c1.join(['type=spinedit', 'pos=180,276,240,0', 'props=1,6,1', 'val='+s_label])]

             +[c1.join(['type=check', 'pos=6,308,148,0', 'cap=Use old LIST command', 'val='+s_uselist])]

             +[c1.join(['type=button', 'pos=300,330,394,0', 'cap=&OK', 'props=1'])]
             +[c1.join(['type=button', 'pos=400,330,490,0', 'cap=Cancel'])]
          ) )
        if res is None: return
        res, s = res
        s = s.splitlines()

        s_type = 'ftp' if s[RES_TYPE_FTP]=='1' else 'sftp' if s[RES_TYPE_SFTP]=='1' else ''
        s_host = s[RES_HOST]
        s_port = s[RES_PORT]
        s_username = s[RES_USERNAME]
        s_password = s[RES_PASS] if s[RES_PASS_ASK]=='0' else '?'
        s_dir = s[RES_DIR]
        s_timeout = s[RES_TIMEOUT]
        s_label = s[RES_LABEL]
        s_uselist = s[RES_USELIST]

        if res == RES_PASS_DEFAULT:
            s_username = 'anonymous'
            s_password = 'user@aol.com'
            continue

        if res == RES_OK:
            if not s_host:
                msg_box('Fill the Host field', MB_OK)
                continue
            if not s_username:
                msg_box('Fill the Username field', MB_OK)
                continue
            return (s_type, s_host, s_port, s_username, s_password, s_dir, s_timeout, s_label, s_uselist)

        else:
            return
