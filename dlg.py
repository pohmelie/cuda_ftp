import os
from cudatext import *

from cudax_lib import get_translation
_   = get_translation(__file__)  # I18N

VK_ENTER = 13

def dialog_server_props(s_type, s_host, s_port,
                        s_username, s_password, s_dir, s_timeout,
                        s_label, s_uselist, s_pkey):
    
    names = [   'type_ftp', 'type_sftp',    'host', 'port',
                'username', 'pass',         'dir',  'timeout',
                'menu_ind', 'use_list',     'pkey', 'ask']
    future_result = [None] # m_ok() fills    
                                
    scale_p, scale_font_p = app_proc(PROC_CONFIG_SCALE_GET, '')
    scale = scale_p*0.01

    h = dlg_proc(0, DLG_CREATE)
    dlg_proc(h, DLG_PROP_SET, prop={
                'cap': _('FTP server info'),
                'border': DBORDER_SIZE,
                'w_min': round(550*scale),
                'autosize': True,
    })
                    
    ### Callbacks (need 'h') 
    def m_reset_auth(*args, **vargs): #SKIP
        dlg_proc(h, DLG_CTL_PROP_SET, name='username', prop={'val': 'anonymous'})
        dlg_proc(h, DLG_CTL_PROP_SET, name='pass', prop={'val': 'user@aol.com'})
        
    def m_choose_pkey_file(*args, **vargs): #SKIP
        info = dlg_proc(h, DLG_CTL_PROP_GET, name='pkey')
        path = info['val']
        path = os.path.dirname(path)  if path else  os.path.expanduser('~')
        caption = _('Choose private key file')
        fn = dlg_file(is_open=True, init_filename='', init_dir=path, filters='', caption=caption)
        if fn:
            if Misc.is_puttygen_key(fn):
                msg = _('You chose a private key in the PuTTYgen format,\nwhich is not supported.\n'
                        'You need to convert it to the OpenSSH format first.\nPuTTYgen can accomplish that.')
                res = msg_box(msg, MB_OK | MB_ICONWARNING)
            dlg_proc(h, DLG_CTL_PROP_SET, name='pkey', prop={'val': fn})
        
    def m_ok(*args, **vargs): #SKIP
        vals = {}
        for name in names:
            info = dlg_proc(h, DLG_CTL_PROP_GET, name=name)
            vals[name] = info['val']
        
        s_type = 'ftp' if vals['type_ftp']=='1' else  ('sftp' if vals['type_sftp']=='1' else '')
        s_host = vals['host']
        s_port = vals['port']
        s_username = vals['username']
        s_password = vals['pass'] if vals['ask']=='0' else '?'
        s_dir = vals['dir']
        s_timeout = vals['timeout']
        s_label = vals['menu_ind']
        s_uselist = vals['use_list']=='1'
        s_pkey = vals['pkey']
        
        if not s_host:
            msg_box(_('Fill the Host field'), MB_OK)
            return
        if not s_username:
            msg_box(_('Fill the Username field'), MB_OK)
            return
            
        future_result[0] = (s_type, s_host, s_port, s_username, s_password, s_dir, s_timeout, s_label, s_uselist, s_pkey)
        
        dlg_proc(h, DLG_HIDE)
            
        
    ### Controls
    label_defaults = {
                'w_min': round(150*scale),  
                'sp_a': round(3*scale),  
                'sp_t': round(6*scale),
    }
    edit_defaults = {
                #'w_min': 320,
                'sp_a': round(3*scale),
    }

    ## main group
    name = 'main_gr'
    n = dlg_proc(h, DLG_CTL_ADD, 'group')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                'name': name,
                'a_l': ('','['),
                'a_t': ('','['),
                'a_r': ('',']'),
                'a_b': None,
                'sp_a': 3,
                'autosize': True,
                'cap': _('Server'),
    })     
    
    # type
    name = 'type_label'
    n = dlg_proc(h, DLG_CTL_ADD, 'label')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **label_defaults,
                'name': name,
                'sp_t': label_defaults['sp_t'] - 2,
                'p': 'main_gr',
                'a_l': ('', '['), 
                'a_t': ('','['),
                'cap': _('Server Type: '),  
    })
    prev_name,name = name, 'type_ftp'
    n = dlg_proc(h, DLG_CTL_ADD, 'radio')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                'name': name,
                'p': 'main_gr',
                'a_l': (prev_name, ']'),
                'a_t': (prev_name,'-'),
                'w_min': round(60*scale),
                'sp_a': round(3*scale),
                'cap': 'FTP',
                'val': '1' if s_type=='ftp' else '0',
    })
    prev_name,name = name, 'type_sftp'
    n = dlg_proc(h, DLG_CTL_ADD, 'radio')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                'name': name,
                'p': 'main_gr',
                'a_l': (prev_name, ']'),
                'a_t': (prev_name,'-'),
                'w_min': round(60*scale),
                'sp_a': round(3*scale),
                'cap': 'SFTP',
                'val': '1' if s_type=='sftp' else '0',
    })
                    
    # host
    prev_name,name = name, 'host_label'
    n = dlg_proc(h, DLG_CTL_ADD, 'label')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **label_defaults,
                'name': name,
                'p': 'main_gr',
                'a_l': ('', '['), 
                'a_t': (prev_name,']'),
                'cap': _('Host: '),  
    })
    prev_name,name = name, 'host'
    n = dlg_proc(h, DLG_CTL_ADD, 'edit')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **edit_defaults,
                'name': name,
                'p': 'main_gr',
                'a_l': (prev_name, ']'),
                'a_t': (prev_name,'-'),
                'a_r': ('',']'),
                'val': s_host,
    })
                    
    # port
    prev_name,name = name, 'port_label'
    n = dlg_proc(h, DLG_CTL_ADD, 'label')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **label_defaults,
                'name': name,
                'p': 'main_gr',
                'a_l': ('', '['), 
                'a_t': (prev_name,']'),
                'cap': _('Port: '),  
    })
    prev_name,name = name, 'port'
    n = dlg_proc(h, DLG_CTL_ADD, 'edit')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **edit_defaults,
                'name': name,
                'p': 'main_gr',
                'w_min': round(60*scale),
                'w': round(60*scale),
                'a_l': (prev_name, ']'),
                'a_t': (prev_name,'-'),
                'a_r': None,
                'val': s_port,
    })
    
    ## AUTH group
    prev_name,name = 'main_gr', 'auth_gr'
    n = dlg_proc(h, DLG_CTL_ADD, 'group')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                'name': name,
                'a_l': ('','['),
                'a_t': (prev_name,']'),
                'a_r': ('',']'),
                'sp_a': round(3*scale),
                'autosize': True,
                'cap': _('Authentication'),
    })       
    
    # username
    prev_name,name = name, 'username_label'
    n = dlg_proc(h, DLG_CTL_ADD, 'label')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **label_defaults,
                'name': name,
                'sp_t': label_defaults['sp_t'] - 2,
                'p': 'auth_gr',
                'a_l': ('', '['), 
                'a_t': ('','['),
                'cap': _('Username: '),  
    })
    prev_name,name = name, 'username'
    n = dlg_proc(h, DLG_CTL_ADD, 'edit')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **edit_defaults,
                'name': name,
                'p': 'auth_gr',
                'a_l': (prev_name, ']'),
                'a_t': (prev_name,'-'),
                'a_r': ('',']'),
                'val': s_username,
    })
    
    # password
    prev_name,name = name, 'pass_label'
    n = dlg_proc(h, DLG_CTL_ADD, 'label')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **label_defaults,
                'name': name,
                'p': 'auth_gr',
                'a_l': ('', '['), 
                'a_t': (prev_name,']'),
                'cap': _('Password: '),  
    })
    prev_name,name = name, 'pass'
    n = dlg_proc(h, DLG_CTL_ADD, 'edit_pwd')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **edit_defaults,
                'name': name,
                'p': 'auth_gr',
                'a_l': (prev_name, ']'),
                'a_t': (prev_name,'-'),
                'a_r': ('',']'),
                'val': s_password if s_password!='?' else '',
    })
    
    prev_name,name = name, 'reset_login'
    n = dlg_proc(h, DLG_CTL_ADD, 'button')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                'name': name,
                'p': 'auth_gr',
                'a_l': (prev_name, '['),
                'a_t': (prev_name,']'),
                'a_r': None,
                'sp_a': round(3*scale),
                'sp_l': round(-3*scale),
                'autosize': True,
                'cap': _('Default anonymous login'),
                'on_change': m_reset_auth,
    })
    
    prev_name,name = name, 'ask'
    n = dlg_proc(h, DLG_CTL_ADD, 'check')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                'name': name,
                'p': 'auth_gr',
                'a_l': (prev_name, '['),
                'a_t': (prev_name,']'),
                'a_r': None,
                'sp_a': round(3*scale),
                'autosize': True,
                'cap': _('Ask password every time'),
                'val': '1' if s_password=='?' else '0',
    })
 
    # pkey
    prev_name,name = name, 'pkey_label'
    n = dlg_proc(h, DLG_CTL_ADD, 'label')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **label_defaults,
                'name': name,
                'p': 'auth_gr',
                'a_l': ('', '['), 
                'a_t': (prev_name,']'),
                'cap': _('or Private key: '),  
    })
    prev_name,name = name, 'pkey_choose'
    n = dlg_proc(h, DLG_CTL_ADD, 'button')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                'name': name,
                'p': 'auth_gr',
                'a_l': None,
                'a_t': (prev_name,'-'),
                'a_r': ('', ']'),
                'sp_a': round(3*scale),
                'autosize': True,
                'cap': _('Choose file...'),
                'on_change': m_choose_pkey_file,
    })
    prev_name,name = name, 'pkey'
    n = dlg_proc(h, DLG_CTL_ADD, 'edit')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **edit_defaults,
                'name': name,
                'p': 'auth_gr',
                'a_l': ('pkey_label', ']'),
                'a_t': (prev_name,'-'),
                'a_r': (prev_name, '['),
                'texthint': _('In OpenSSH format, not .ppk'),
                'val': s_pkey,
    })
    
 
    ## MISC group
    prev_name,name = 'auth_gr', 'misc_group'
    n = dlg_proc(h, DLG_CTL_ADD, 'group')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                'name': name,
                'a_l': ('','['),
                'a_t': (prev_name,']'),
                'a_r': ('',']'),
                'sp_a': round(3*scale),
                'autosize': True,
                'cap': _('Misc'),
    })                       
    # initial dir
    prev_name,name = 'auth_gr', 'dir_label'
    n = dlg_proc(h, DLG_CTL_ADD, 'label')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **label_defaults,
                'name': name,
                'p': 'misc_group',
                'sp_t': label_defaults['sp_t'] - 2,
                'a_l': ('', '['), 
                'a_t': ('','['),
                'cap': _('Initial remote dir: '),  
    })
    prev_name,name = name, 'dir'
    n = dlg_proc(h, DLG_CTL_ADD, 'edit')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **edit_defaults,
                'name': name,
                'p': 'misc_group',
                'a_l': (prev_name, ']'),
                'a_t': (prev_name,'-'),
                'a_r': ('',']'),
                'val': s_dir,
    })
                    
    # timeout
    prev_name,name = name, 'timeout_label'
    n = dlg_proc(h, DLG_CTL_ADD, 'label')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **label_defaults,
                'name': name,
                'p': 'misc_group',
                'a_l': ('', '['), 
                'a_t': (prev_name,']'),
                'cap': _('Timeout (seconds): '),  
    })
    prev_name,name = name, 'timeout'
    n = dlg_proc(h, DLG_CTL_ADD, 'spinedit')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                'name': name,
                'p': 'misc_group',
                'a_l': (prev_name, ']'),
                'a_t': (prev_name,'-'),
                'a_r': None,
                'sp_a': round(3*scale),
                'w_min': round(50*scale),
                'ex0': 1, # min
                'ex1': 120, # max
                'ex2': 1, # increment
                'val': s_timeout,
    })                       
                    
    # menu label
    prev_name,name = name, 'menu_ind_label'
    n = dlg_proc(h, DLG_CTL_ADD, 'label')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **label_defaults,
                'name': name,
                'p': 'misc_group',
                'a_l': ('', '['), 
                'a_t': (prev_name,']'),
                'cap': _('Label (for menu): '), 
    })
    prev_name,name = name, 'menu_ind'
    n = dlg_proc(h, DLG_CTL_ADD, 'spinedit')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **edit_defaults,
                'name': name,
                'p': 'misc_group',
                'a_l': (prev_name, ']'),
                'a_t': (prev_name,'-'),
                'a_r': None,
                'sp_a': round(3*scale),
                'w_min': round(50*scale),
                'ex0': 1, # min
                'ex1': 6, # max
                'ex2': 1, # increment 
                'val': s_label,
    })                       
    
    prev_name,name = name, 'use_list'
    n = dlg_proc(h, DLG_CTL_ADD, 'check')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                'name': name,
                'p': 'misc_group',
                'a_l': ('', '['),
                'a_t': (prev_name,']'),
                'a_r': None,
                'sp_a': round(3*scale),
                'autosize': True,
                'cap': _('Use old LIST command'), 
                'val': '1' if s_uselist else '0',
    })
    
                    
    # Cancel | Ok
    prev_name,name = 'misc_group', 'ok'        
    n_ok = dlg_proc(h, DLG_CTL_ADD, 'button')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n_ok, prop={
                'name': name,
                'a_l': None,
                'a_t': (prev_name, ']'),
                'a_r': ('', ']'),
                'a_b': ('',']'),
                'w_min': round(60*scale),
                'sp_a': round(6*scale),
                'autosize': True,
                'cap': _('OK'),  
                'on_change': m_ok,
    })
                    
    prev_name,name = name, 'cancel'        
    n_cancel = dlg_proc(h, DLG_CTL_ADD, 'button')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n_cancel, prop={
                'name': name,
                'a_l': None,
                'a_t': (prev_name, '['),
                'a_r': (prev_name, '['),
                'a_b': (prev_name,']'),
                'w_min': round(60*scale),
                #'sp_a': round(6*scale),
                'autosize': True,
                'cap': _('Cancel'),  
                'on_change': lambda *args, h_dlg=h, **vargs: dlg_proc(h_dlg, DLG_HIDE),
    })
                
    dlg_proc(h, DLG_SCALE)
    dlg_proc(h, DLG_SHOW_MODAL)
    
    dlg_proc(h, DLG_FREE)
    
    return future_result[0]
            

def dlg_password(title, label):
    future_result = [None]
    
    scale_p, scale_font_p = app_proc(PROC_CONFIG_SCALE_GET, '')
    scale = scale_p*0.01
    
    defaults = { 
                'sp_a': 4, 
                'w_min': 60,
    }
    defaults = {k:round(v*scale) for k,v in defaults.items()}
    
            
    def m_ok(*args, **vargs): #SKIP
        info = dlg_proc(h, DLG_CTL_PROP_GET, name='edit')
        
        future_result[0] = info['val']
        
        dlg_proc(h, DLG_HIDE)
        
    def on_key_down(id_dlg, id_ctl, data='', info=''): #SKIP
        if (id_ctl==VK_ENTER) and (data==''):
            m_ok()
            return False
        
    
    h = dlg_proc(0, DLG_CREATE)
    dlg_proc(h, DLG_PROP_SET, prop={
                'cap': title,
                'border': DBORDER_SIZE,
                'w_min': round(400*scale),
                'autosize': True,
                'keypreview': True,
                'on_key_down': on_key_down,
    })
    
    name = 'label',
    n = dlg_proc(h, DLG_CTL_ADD, 'label')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **defaults,
                'name': name,
                #'sp_t': label_defaults['sp_t'] - 2,
                'a_l': ('', '['), 
                'a_t': ('','['),
                'a_r': ('',']'),
                'a_b': None,
                'cap': label,  
    })
    prev_name,name = name, 'edit'
    n = dlg_proc(h, DLG_CTL_ADD, 'edit_pwd')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n, prop={
                **defaults,
                'name': name,
                'a_l': ('', '['), 
                'a_t': (prev_name,']'),
                'a_r': ('',']'),
                'a_b': None,
    })
                    
                    
    # Cancel | Ok
    prev_name,name = name, 'ok'        
    n_ok = dlg_proc(h, DLG_CTL_ADD, 'button')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n_ok, prop={
                **defaults,
                'name': name,
                'a_l': None,
                'a_t': (prev_name, ']'),
                'a_r': ('', ']'),
                'a_b': ('',']'),
                'autosize': True,
                'cap': _('&OK'),  
                'on_change': m_ok,
    })
                    
    prev_name,name = name, 'cancel'        
    n_cancel = dlg_proc(h, DLG_CTL_ADD, 'button')
    dlg_proc(h, DLG_CTL_PROP_SET, index=n_cancel, prop={
                **defaults, 
                'name': name,
                'sp_a': None,
                'a_l': None,
                'a_t': (prev_name, '['),
                'a_r': (prev_name, '['),
                'a_b': (prev_name, ']'),
                'autosize': True,
                'cap': _('&Cancel'),  
                'on_change': lambda *args, h_dlg=h, **vargs: dlg_proc(h_dlg, DLG_HIDE),
    })
    
    
    dlg_proc(h, DLG_SCALE)
    dlg_proc(h, DLG_SHOW_MODAL)
    
    dlg_proc(h, DLG_FREE)
    
    return future_result[0]

class Misc:
    # https://tartarus.org/~simon/putty-snapshots/htmldoc/AppendixC.html#ppk-outer
    PUTTY_KEY_HEADER = 'PuTTY-User-Key-File-'
    
    def is_puttygen_key(filepath):
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return f.readline().startswith(Misc.PUTTY_KEY_HEADER)


