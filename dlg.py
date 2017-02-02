from cudatext import *

def dialog_server_props(s_type, s_host, s_port, s_username, s_password, s_dir, s_timeout, s_label):

    if app_api_version()<'1.0.165':
        msg_box('FTP plugin needs newer app version', MB_OK+MB_ICONERROR)
        return
    
    RES_TYPE_FTP = 1
    RES_TYPE_SFTP = 2
    RES_HOST = 4
    RES_PORT = 6
    RES_USERNAME = 8
    RES_PASS = 10
    RES_PASS_ASK = 11
    RES_DIR = 13
    RES_TIMEOUT = 15 
    RES_LABEL = 17
    RES_OK = 18
    
    c1 = chr(1)
    res = dlg_custom('FTP server info', 496, 360, 
      '\n'.join([]
         +[c1.join(['type=label', 'pos=6,8,190,0', 'cap=Server type:'])]
         +[c1.join(['type=radio', 'pos=180,6,290,0', 'cap=FTP', 'val='+('1' if s_type=='ftp' else '0') ])]
         +[c1.join(['type=radio', 'pos=250,6,390,0', 'cap=SFTP', 'val='+('1' if s_type=='sftp' else '0')])]
         
         +[c1.join(['type=label', 'pos=6,38,148,0', 'cap=Host (e.g. ftp.site.com):'])]
         +[c1.join(['type=edit', 'pos=180,36,490,0', 'val='+s_host])]

         +[c1.join(['type=label', 'pos=6,68,148,0', 'cap=Port:'])]
         +[c1.join(['type=edit', 'pos=180,66,240,0', 'val='+s_port])]

         +[c1.join(['type=label', 'pos=6,98,148,0', 'cap=Username:'])]
         +[c1.join(['type=edit', 'pos=180,96,490,0', 'val='+s_username])]

         +[c1.join(['type=label', 'pos=6,128,148,0', 'cap=Password:'])]
         +[c1.join(['type=edit_pwd', 'pos=180,126,490,0', 'val='+(s_password if s_password!='?' else '') ])]
         +[c1.join(['type=check', 'pos=180,156,490,0', 'cap=Ask password every time', 'val='+('1' if s_password=='?' else '0') ])]

         +[c1.join(['type=label', 'pos=6,188,148,0', 'cap=Initial remote dir:'])]
         +[c1.join(['type=edit', 'pos=180,186,490,0', 'val='+s_dir])]

         +[c1.join(['type=label', 'pos=6,218,148,0', 'cap=Timeout (seconds):'])]
         +[c1.join(['type=spinedit', 'pos=180,216,240,0', 'props=1,120,1', 'val='+s_timeout])]

         +[c1.join(['type=label', 'pos=6,248,148,0', 'cap=Label (for menu):'])]
         +[c1.join(['type=spinedit', 'pos=180,246,240,0', 'props=1,6,1', 'val='+s_label])]

         +[c1.join(['type=button', 'pos=300,330,394,0', 'cap=&OK', 'props=1'])]
         +[c1.join(['type=button', 'pos=400,330,490,0', 'cap=Cancel'])]
      ) )
    if res is None: return
        
    res, s = res
    if res != RES_OK: return
    
    s = s.splitlines()
    return (
        'ftp' if s[RES_TYPE_FTP=='1'] else 'sftp' if s[RES_TYPE_SFTP]=='1' else '',
        s[RES_HOST],
        s[RES_PORT],
        s[RES_USERNAME],
        s[RES_PASS] if s[RES_PASS_ASK]=='0' else '?',
        s[RES_DIR],
        s[RES_TIMEOUT],
        s[RES_LABEL]
        )
