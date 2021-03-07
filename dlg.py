import os
from cudatext import *

is_unix = os.name!='nt'

def dialog_server_props(s_type, s_host, s_port,
                        s_username, s_password, s_dir, s_timeout,
                        s_label, s_uselist, s_pkey):

    RES_TYPE_FTP = 1
    RES_TYPE_SFTP = 2
    RES_HOST = 4
    RES_PORT = 6
    RES_USERNAME = 9
    RES_PASS = 11
    RES_PASS_DEFAULT = 12
    RES_PASS_ASK = 13
    RES_PRIVATE_KEY = 15
    RES_PRIVATE_KEY_CHOOSE = 16

    RES_DIR = 18
    RES_TIMEOUT = 20
    RES_LABEL = 22
    RES_USELIST = 23
    RES_OK = 24

    c1 = chr(1)
    while True:
        res = dlg_custom('FTP server info', 496, 380+32,
          '\n'.join([]
             +[c1.join(['type=label', 'pos=6,8,190,0', 'cap=Server type:'])]
             +[c1.join(['type=radio', 'pos=180,6,250,0', 'cap=FTP', 'val='+('1' if s_type=='ftp' else '0') ])]
             +[c1.join(['type=radio', 'pos=250,6,350,0', 'cap=SFTP', 'val='+('1' if s_type=='sftp' else '0') ])]

             +[c1.join(['type=label', 'pos=6,38,148,0', 'cap=Host (e.g. ftp.site.com):'])]
             +[c1.join(['type=edit', 'pos=180,36,490,0', 'val='+s_host])]

             +[c1.join(['type=label', 'pos=6,68,148,0', 'cap=Port:'])]
             +[c1.join(['type=edit', 'pos=180,66,240,0', 'val='+s_port])] # 6

             +[c1.join(['type=group', 'name=group', 'pos=6,92,490,244'])]

               +[c1.join(['type=label', 'p=group', 'pos=6,6,148,0', 'cap=Username:'])]
               +[c1.join(['type=edit', 'p=group', 'pos=172,4,474,0', 'val='+s_username])] # 9

               +[c1.join(['type=label', 'p=group', 'pos=6,36,148,0', 'cap=Password:'])]
               +[c1.join(['type=edit_pwd', 'p=group', 'pos=172,34,474,0', 'val='+(s_password if s_password!='?' else '') ])]
               +[c1.join(['type=button', 'p=group', 'pos=172,64,380,0', 'cap=Default anonymous login' ])] # 12
               +[c1.join(['type=check', 'p=group', 'pos=172,92,474,0', 'cap=Ask password every time', 'val='+('1' if s_password=='?' else '0') ])]

               +[c1.join(['type=label', 'p=group', 'pos=6,122,148,0', 'cap=or Private key:'])]
               +[c1.join(['type=edit', 'p=group', 'pos=172,120,380,0', 'val='+s_pkey])] # 15
               +[c1.join(['type=button', 'p=group', 'pos=384,118,474,0', 'cap=Choose file...' ])]

             +[c1.join(['type=label',   'pos=6,250,148,0', 'cap=Initial remote dir:'])]
             +[c1.join(['type=edit',    'pos=180,248,490,0', 'val='+s_dir])]

             +[c1.join(['type=label',   'pos=6,280,148,0', 'cap=Timeout (seconds):'])]
             +[c1.join(['type=spinedit','pos=180,278,240,0', 'ex0=1', 'ex1=120', 'ex2=1', 'val='+s_timeout])]

             +[c1.join(['type=label',   'pos=6,310,148,0', 'cap=Label (for menu):'])]
             +[c1.join(['type=spinedit','pos=180,308,240,0', 'ex0=1', 'ex1=6', 'ex2=1', 'val='+s_label])]

             +[c1.join(['type=check',   'pos=6,340,300,0', 'cap=Use old LIST command', 'val='+('1' if s_uselist else '0') ])]

             +[c1.join(['type=button', 'pos=300,382,394,0', 'cap=&OK', 'ex0=1'])]
             +[c1.join(['type=button', 'pos=400,382,490,0', 'cap=Cancel'])]
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
        s_uselist = s[RES_USELIST]=='1'
        s_pkey = s[RES_PRIVATE_KEY]

        if res == RES_PASS_DEFAULT:
            s_username = 'anonymous'
            s_password = 'user@aol.com'
            continue

        if res == RES_PRIVATE_KEY_CHOOSE:
            homedir = os.path.expanduser('~')
            caption = 'Choose private key file'
            fn = dlg_file(is_open=True, init_filename='', init_dir=homedir, filters='', caption=caption)
            if fn:
                s_pkey = fn
            continue

        if res == RES_OK:
            if not s_host:
                msg_box('Fill the Host field', MB_OK)
                continue
            if not s_username:
                msg_box('Fill the Username field', MB_OK)
                continue
            return (s_type, s_host, s_port, s_username, s_password, s_dir, s_timeout, s_label, s_uselist, s_pkey)

        else:
            return

def dlg_password(title, label):
    RES_PASS = 1
    RES_OK = 2

    c1 = chr(1)
    res = dlg_custom(title, 400, 86,
        '\n'.join([]
            +[c1.join(['type=label', 'pos=6,8,394,0', 'cap='+label])]
            +[c1.join(['type=edit_pwd', 'pos=6,24,394,0'])] # 1

            +[c1.join(['type=button', 'pos=200,55,294,0', 'cap=&OK', 'ex0=1'])] # 2
            +[c1.join(['type=button', 'pos=300,55,394,0', 'cap=Cancel'])]
    ))
    if res is None: return
    res, s = res
    s = s.splitlines()

    s_pwd = s[RES_PASS]

    if res == RES_OK:
        return s_pwd
