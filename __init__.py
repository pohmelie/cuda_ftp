# -*- encoding: utf-8 -*-
import sys
import os
import platform
import collections
import contextlib
import json
import tempfile
import socket
import stat
from ftplib import FTP, error_perm
from .pathlib import Path, PurePosixPath
from datetime import datetime
from .dlg import *
import hashlib
import base64
import math

#for Windows, use portable installation of Paramiko+others
v = sys.version_info
v = str(v[0])+str(v[1])
if os.name=='nt':
    if platform.architecture()[0] == '32bit':
        dirname = 'x32'
    else:
        dirname = 'x64'
    sys.path.append(os.path.join(app_path(APP_DIR_PY), 'cuda_ftp_libs_py'+v, dirname))

try:
    import paramiko
except ImportError:
    paramiko = None

from cudatext import *
from cudatext_keys import *
import cudatext_cmd

from cudax_lib import get_translation
_ = get_translation(__file__)  # I18N

# Create panel in the bottom for logging
TITLE_LOG = _("FTP Log")
handle_log = 0

def init_log():
    global handle_log
    if handle_log: return

    h_dlg = dlg_proc(0, DLG_CREATE)

    n = dlg_proc(h_dlg, DLG_CTL_ADD, prop='listbox_ex')
    dlg_proc(h_dlg, DLG_CTL_PROP_SET, index=n, prop={
        'name':'list',
        'a_r':('',']'), #anchor to entire form: l,r,t,b
        'a_b':('',']'),
        } )

    handle_log = dlg_proc(h_dlg, DLG_CTL_HANDLE, index=n)

    dlg_proc(h_dlg, DLG_SCALE)
    listbox_proc(handle_log, LISTBOX_THEME) #THEME after DLG_SCALE

    app_proc(PROC_BOTTOMPANEL_ADD_DIALOG, (TITLE_LOG, h_dlg, 'ftp log.png'))


# Show ftp exceptions in Console panel (download/upload/etc)
# Not good since errors shown in FTP Log panel anyway
SHOW_EX = False

# temp storage of password inputs
pass_inputs = {}
# temp storage of password inputs for private keys
pkeys_pass = {}

''' file:///install.inf
'''

def server_address(server):
    return server.get("address", "")


def server_login(server):
    return server.get("login", "")


def server_password(server, can_input=True):
    s = server.get("password", "")
    if s == '?' and can_input:
        title = server_alias(server)
        s = pass_inputs.get(title, '')
        if s:
            return s

        s = dlg_password('CudaText', _('Password for {}:').format(title))
        if not s:
            raise Exception('Password input cancelled')
        pass_inputs[title] = s
    return s


def server_init_dir(server):
    return server.get("init_dir", "")


def server_timeout(server):
    s = server.get("timeout", "")
    if s.isdigit():
        return s
    else:
        return "30"


def server_port(server):
    s = server.get("port", "")
    if s.isdigit():
        return s
    else:
        if server_type(server) == 'ftp':
            return '21'
        else:
            return '22'


def server_type(server):
    s = server.get("type", "")
    if s not in ('ftp', 'sftp'):
        s = 'ftp'
    return s


def server_label(server):
    return server.get("label", "")


def server_pkey_path(server):
    return server.get("pkey_path", "")


def server_remote_cert_fp(server):
    return server.get("remote_cert_fingerprint", "")


def server_use_list(server):
    return server.get("use_list", False)


def server_alias(server):
    return server.get('alias')


def server_title(server):
    return "{}://{}:{}@{}".format(
        server_type(server),
        server_address(server),
        server_port(server),
        server_login(server),
    )


def server_alias_candidates(server):
    title = server_title(server)
    yield title
    yield from ('{} {}'.format(title, i) for i in range(2, 2**30))


def dialog_server(init_server=None):
    """
    Must give dict, which can be parsed by server_nnnnn(), or None
    """
    _typ = server_type(init_server) if init_server else "ftp"
    _host = server_address(init_server) if init_server else ""
    _port = server_port(init_server) if init_server else ""
    _username = server_login(init_server) if init_server else "anonymous"
    _pass = server_password(init_server, False) if init_server else "user@aol.com"
    _dir = server_init_dir(init_server) if init_server else ""
    _time = server_timeout(init_server) if init_server else "30"
    _label = server_label(init_server) if init_server else ""
    _uselist = server_use_list(init_server) if init_server else False
    _pkey = server_pkey_path(init_server) if init_server else ""
    _remote_cert_fp = server_remote_cert_fp(init_server) if init_server else ""

    res = dialog_server_props(_typ, _host, _port, _username, _pass, _dir, _time, _label, _uselist,
                _pkey)
    if res is None:
        return

    data = dict(zip((
        "type",
        "address",
        "port",
        "login",
        "password",
        "init_dir",
        "timeout",
        "label",
        "use_list",
        "pkey_path",
        ), res))
    data["remote_cert_fingerprint"] = _remote_cert_fp
    return data

def get_fingerprint(crypt_type, key_bytes=None, key_str=None):
    if key_bytes is None:
        key_bytes = base64.b64decode(key_str)

    if crypt_type == 'md5':
        h = hashlib.md5()
    elif crypt_type == 'sha1':
        h = hashlib.sha1()

    h.update(key_bytes)
    hexdigest = h.hexdigest().upper()
    fingerprint = ' '.join([hexdigest[i*2:i*2+2] for i in range(len(hexdigest)//2)])
    return fingerprint

class SFTP:
    OK = 'sftp_ok'
    CONFIRM_FIRST_CONNECTION_CERT = 'pkey_first_conn'
    NEW_REMOTE_CERT_WARN = 'pkey_remote_cert_changed'

    if paramiko:
        PK_TYPES = [
            paramiko.rsakey.RSAKey,
            paramiko.ed25519key.Ed25519Key,
            paramiko.ecdsakey.ECDSAKey,
            paramiko.dsskey.DSSKey,
        ]
    else:
        raise Exception('Paramiko is not installed')

    def connect(self, address, port, timeout=None):
        self.address = address
        self.port = port
        self.sock = socket.create_connection((address, port), timeout=timeout)
        self.transport = paramiko.transport.Transport(self.sock)

    def login(self, username, password, pkey_path, remote_cert_fp):
        if pkey_path: # login with private key
            pkey = self._get_private_key(username, pkey_path)

            self.transport.connect(None, username, pkey=pkey)

            servkey = self.transport.get_remote_server_key()
            r_remote_cert = servkey.asbytes()

            r_remote_cert_fp = get_fingerprint('sha1', key_bytes=r_remote_cert)

            if not remote_cert_fp: # first conenction
                yield (SFTP.CONFIRM_FIRST_CONNECTION_CERT, r_remote_cert)
            elif remote_cert_fp != r_remote_cert_fp: # remote server certificate changed
                yield (SFTP.NEW_REMOTE_CERT_WARN,          r_remote_cert)
            else:
                yield SFTP.OK

        else: # login with password
            self.transport.connect(None, username, password)

        self.sftp = self.transport.open_sftp_client()
        yield None

    def quit(self):
        self.sftp.close()
        self.transport.close()

    # The MLSD command is a replacement for the LIST command that is meant to
    #   standardize the format for directory listings
    def mlsd(self, path, use_list=False):
        for info in self.sftp.listdir_iter(str(path)):
            if stat.S_ISDIR(info.st_mode):
                yield info.filename, dict(type="dir", size=info.st_size)
            elif stat.S_ISREG(info.st_mode):
                yield info.filename, dict(type="file", size=info.st_size)

    def retrbinary(self, command, callback):
        path = command.lstrip("RETR ")
        with self.sftp.open(path, mode="r") as fin:
            while True:
                data = fin.read(8192)
                if not data:
                    break

                callback(data)

    def storbinary(self, command, fin):
        path = command.lstrip("STOR ")
        self.sftp.putfo(fin, path)

    def mkd(self, path):
        try:
            self.sftp.mkdir(path)
        except OSError:
            raise error_perm

    def rmd(self, path):
        self.sftp.rmdir(path)

    def delete(self, path):
        self.sftp.remove(path)

    def _get_private_key(self, username, pkey_path):
        i = 0
        while i < len(SFTP.PK_TYPES):
            PKeyType = SFTP.PK_TYPES[i]
            i += 1
            with open(pkey_path, 'r', encoding='utf-8') as f:
                try:
                    pkey = PKeyType.from_private_key(f, password=pkeys_pass.get(pkey_path))
                    break
                except paramiko.ssh_exception.PasswordRequiredException:
                    title = "sftp://{}@{}:{}".format(username, self.address, self.port)
                    res = dlg_password(title, _("Enter private key passphrase:"))
                    if res:
                        i -= 1 # repeat same PKeyType
                        pkeys_pass[pkey_path] = res
                        continue
                    else:
                        pkey = None
                        break
                except paramiko.ssh_exception.SSHException: # wrong key type  or  wrong|need passphrase
                    pkey = None
                    continue

        if pkey is None:
            if pkey_path in pkeys_pass:
                del pkeys_pass[pkey_path] # same exception for wrong pass or wronk keyType
            raise Exception('Failed to load private key!')
        return pkey


def parse_list_line(b, encoding="utf-8"):
    """
    Attempt to parse a LIST line (just type and name).

    :param b: response line
    :type b: :py:class:`bytes` or :py:class:`str`

    :param encoding: encoding to use
    :type encoding: :py:class:`str`

    :return: (path, info)
    :rtype: (:py:class:`pathlib.PurePosixPath`, :py:class:`dict`)
    """
    if isinstance(b, bytes):
        s = b.decode(encoding=encoding)
    else:
        s = b
    s = s.rstrip()
    info = {}
    if s[0] == "-":
        info["type"] = "file"
    elif s[0] == "d":
        info["type"] = "dir"
    elif s[0] == "l":
        info["type"] = "link"
    else:
        info["type"] = "unknown"

    s = s[10:].lstrip()
    for xx in range(4):
        i = s.index(" ")
        s = s[i:].lstrip()
    s = s[12:].strip()
    if info["type"] == "link":
        i = s.rindex(" -> ")
        s = s[:i]
    return PurePosixPath(s), info


class FTP_:
    def __init__(self):
        self._ftp = FTP()

    def __getattr__(self, name):
        return getattr(self._ftp, name)

    def login(self, username, password, *args):
        self._ftp.login(username, password)
        yield None

    def mlsd(self, path, use_list=False):
        if use_list:
            #show_log('Using old LIST command', str(path))
            paths = []
            self._ftp.encoding = sys.getfilesystemencoding()
            self._ftp.retrlines("LIST {}".format(path), callback=paths.append)
            for path in paths:
                yield parse_list_line(path)

        else:
            # Copied code of FTP.mlsd
            CRLF = '\r\n'
            if path:
                cmd = "MLSD %s" % path
            else:
                cmd = "MLSD"
            lines = []
            self.retrlines(cmd, lines.append)
            for line in lines:
                facts_found, _x, name = line.rstrip(CRLF).partition(' ')
                entry = {}
                for fact in facts_found[:-1].split(";"):
                    key, _xx, value = fact.partition("=")
                    entry[key.lower()] = value
                yield (name, entry)


@contextlib.contextmanager
def CommonClient(server):
    address = server_address(server)
    schema = server_type(server)
    host = server_address(server)
    port = server_port(server)
    timeout = server_timeout(server)
    if schema == "sftp":
        if paramiko is None:
            msg_box(
                _("Please install 'Paramiko' library for SFTP support"),
                MB_OK | MB_ICONERROR,
            )
        client = SFTP()
    elif schema == "ftp":
        client = FTP_()
    else:
        raise Exception("Unknown server type: '{}'".format(schema))

    client.connect(host, int(port), timeout=int(timeout))
    yield client
    client.quit()


def show_log(str1, str2):
    time_fmt = "[%H:%M:%S] "
    time_str = datetime.now().strftime(time_fmt)
    text = time_str + str1 + ": " + str2

    app_proc(PROC_BOTTOMPANEL_ACTIVATE, TITLE_LOG)
    # prev line steals focus from editor on save
    ed.focus()

    listbox_proc(handle_log, LISTBOX_ADD, index=-1, text=text)
    cnt = listbox_proc(handle_log, LISTBOX_GET_COUNT)
    listbox_proc(handle_log, LISTBOX_SET_SEL, index=cnt-1)


NODE_SERVER = 0
NODE_DIR = 1
NODE_FILE = 2

icon_names = {
    NODE_SERVER: "server.png",
    NODE_DIR: "dir.png",
    NODE_FILE: "file.png",
}


NodeInfo = collections.namedtuple("NodeInfo", "caption index image level")


class Command:

    title = "FTP"
    inited = False
    tree = None
    h_dlg = None
    h_menu = None

    actions = {
        None: (
            # patch for translations (fm), see also generate_context_menu()
            #  name,                action_name
            (_("New server"),       "new_server"),
        ),
        NODE_SERVER: (
            (_("New server..."),    "new_server"),
            (_("Edit server..."),   "edit_server"),
            (_("Rename server..."), "rename_server"),
            (_("Remove server"),    "remove_server"),
            ("-",                   ""),
            (_("Go to dir..."),     "go_to_dir"),
            (_("Go to file..."),    "go_to_file"),
            (_("History..."),       "go_to_history"),
            ("-",                   ""),
            (_("New file..."),      "new_file"),
            (_("New dir..."),       "new_dir"),
            (_("Upload here..."),   "upload_here"),
            ("-",                   ""),
            (_("Refresh"),          "refresh"),
        ),
        NODE_DIR: (
            (_("New file..."),      "new_file"),
            (_("New dir..."),       "new_dir"),
            ("-",                   ""),
            (_("Remove"),           "remove_dir"),
            (_("Rename"),           "rename_file_dir"),
            (_("Upload here..."),   "upload_here"),
            ("-",                   ""),
            (_("Copy path"),        "copy_path"),
            (_("Copy link"),        "copy_link"),
            ("-",                   ""),
            (_("Refresh"),          "refresh"),
        ),
        NODE_FILE: (
            (_("Open"),             "open_file"),
            ("-",                   ""),
            (_("Remove..."),        "remove_file"),
            (_("Rename..."),        "rename_file_dir"),
            (_("Download"),         "download_file"),
            (_("Backup..."),        "backup_file"),
            ("-",                   ""),
            (_("Copy path"),        "copy_path"),
            (_("Copy link"),        "copy_link"),
            ("-",                   ""),
            (_("Get properties"),   "get_properties"),
        ),
    }

    def init_options(self):
        self.options = {"servers": []}
        settings_dir = Path(app_path(APP_DIR_SETTINGS))
        self.options_filename = settings_dir / "cuda_ftp.json"
        if self.options_filename.exists():
            with self.options_filename.open() as fin:
                self.options = json.load(fin)

        # give aliases if missing
        aliases = self.list_aliases()
        found_repeated = set()
        for server in self.options["servers"]:
            alias = server_alias(server)
            if alias is None: # no alias - create
                alias = next(al for al in server_alias_candidates(server)  if al not in aliases)
                server['alias'] = alias
                aliases.append(alias)
            elif aliases.count(alias) > 1: # has alias but repeating  (should_never_happen_tm)
                if alias not in found_repeated: # first encounted - skip
                    found_repeated.add(alias)
                else: # already have this alias
                    server['alias'] = next(al for al in server_alias_candidates(server)  if al not in aliases)
                    aliases.append(alias)

        # fill tree
        for server in self.options["servers"]:
            self.action_new_server(server)

        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir_path = Path(self.temp_dir.name)

    def init_panel(self):
        init_log()
        ed.cmd(cudatext_cmd.cmd_ShowSidePanelAsIs)

        self.h_dlg = dlg_proc(0, DLG_CREATE)
        dlg_proc(self.h_dlg, DLG_PROP_SET, prop={
            'keypreview': True,
            'on_key_down': self.form_on_key,
            })

        n = dlg_proc(self.h_dlg, DLG_CTL_ADD, prop='treeview')
        dlg_proc(self.h_dlg, DLG_CTL_PROP_SET, index=n, prop={
            'name': 'tree',
            'a_r': ('',']'),  # anchor to entire form: l,r,t,b
            'a_b': ('',']'),
            'on_menu': 'cuda_ftp.tree_on_menu',
            'on_click_dbl': 'cuda_ftp.tree_on_click_dbl',
        })

        self.tree = dlg_proc(self.h_dlg, DLG_CTL_HANDLE, index=n)
        self.tree_imglist = tree_proc(self.tree, TREE_GET_IMAGELIST)
        tree_proc(self.tree, TREE_PROP_SHOW_ROOT, text='0')

        dlg_proc(self.h_dlg, DLG_SCALE)
        tree_proc(self.tree, TREE_THEME) #TREE_THEME after DLG_SCALE

        app_proc(PROC_SIDEPANEL_ADD_DIALOG, (self.title, self.h_dlg, 'ftp.png'))

        # load icons
        base = Path(__file__).parent
        for n in (NODE_SERVER, NODE_DIR, NODE_FILE):
            path = base / 'icons' / icon_names[n]
            imagelist_proc(self.tree_imglist, IMAGELIST_ADD, value=path)

    def show_panel(self, activate=True):
        if not self.inited:
            self.inited = True
            self.init_panel()
            self.init_options()
        if activate:
            ed.cmd(cudatext_cmd.cmd_ShowSidePanelAsIs)
            app_proc(PROC_SIDEPANEL_ACTIVATE, (self.title, True))
        self.generate_context_menu()

    def show_menu_connect(self):
        if not self.inited:
            self.inited = True
            self.init_panel()
            self.init_options()
        menu_items = [server_alias(server) for server in self.options["servers"]]
        res = dlg_menu(DMENU_LIST, menu_items, caption=_('Connect to server'))
        if res is None:
            return
        self.connect_by_caption(menu_items[res])

    def connect_by_caption(self, item_chosen):
        msg_status(_('Connect to: ')+item_chosen, True)
        self.show_panel(True)
        # find panel item for item_chosen
        items = tree_proc(self.tree, TREE_ITEM_ENUM, 0)
        if not items:
            return
        for item in items:
            item_handle = item[0]
            item_caption = item[1]
            if item_caption == item_chosen:
                tree_proc(self.tree, TREE_ITEM_FOLD_DEEP, 0)
                tree_proc(self.tree, TREE_ITEM_SELECT, item_handle)
                self.action_refresh()
                return

    def connect_label(self, label):
        if not self.inited:
            self.inited = True
            self.init_panel()
            self.init_options()
        for server in self.options["servers"]:
            if server_label(server) == label:
                self.connect_by_caption(server_alias(server))
                return
        else:
            msg_status(_('Cannot find server with label "{}"').format(label))

    def connect_label_1(self):
        self.connect_label('1')

    def connect_label_2(self):
        self.connect_label('2')

    def connect_label_3(self):
        self.connect_label('3')

    def connect_label_4(self):
        self.connect_label('4')

    def connect_label_5(self):
        self.connect_label('5')

    def connect_label_6(self):
        self.connect_label('6')

    @property
    def selected(self):
        return tree_proc(self.tree, TREE_ITEM_GET_SELECTED)

    def get_info(self, index):
        prop = tree_proc(self.tree, TREE_ITEM_GET_PROPS, index)
        return NodeInfo(
            prop['text'],
            prop['index'],
            prop['icon'],
            prop['level']
            )

    def generate_context_menu(self):
        if not self.h_menu:
            self.h_menu = menu_proc(0, MENU_CREATE)
        menu_proc(self.h_menu, MENU_CLEAR)

        if self.selected is not None:
            i = self.get_info(self.selected).image
        else:
            i = None

        # patch for translations (fm)
        for name, action_name in self.actions[i]:
            menu_proc(self.h_menu, MENU_ADD, command="cuda_ftp.action_" + action_name, caption=name)

    def store_file(self, server, server_path, client_path):
        try:
            with CommonClient(server) as client:
                self.login(client, server)

                try:
                    client.mkd(str(server_path.parent))
                except error_perm:
                    pass
                with client_path.open(mode="rb") as fin:
                    client.storbinary("STOR " + str(server_path), fin)

            show_log("[↑] Uploaded", server_address(server) + str(server_path))
        except Exception as ex:
            show_log("Upload file", str(ex))
            if SHOW_EX:
                raise

    def login(self, client, server):
        resgen = client.login(server_login(server), server_password(server),
                    server_pkey_path(server), server_remote_cert_fp(server))

        res = next(resgen)

        if res is None: # FTP
            return
        elif res == SFTP.OK:
            next(resgen)
            return

        try:
            item,data = res[:2]
        except TypeError:
            raise Exception('Login failed!')

        r_remote_cert = data
        sha1_fp = get_fingerprint("sha1", r_remote_cert)
        fingerprints = "[MD5]: {}\n[SHA1]: {}".format(get_fingerprint("md5", r_remote_cert), sha1_fp)
        if item == SFTP.CONFIRM_FIRST_CONNECTION_CERT:
            msg = _("First connection to this host.\nAccept host's certificate?\n\n")+fingerprints
            res = msg_box(msg, MB_OKCANCEL | MB_ICONQUESTION)
            if res == ID_OK:
                server["remote_cert_fingerprint"] = sha1_fp
                self.save_options()
                show_log('Private key Auth', 'Accepted host\'s certificate')
                next(resgen) # continue login process
                return
            else:
                raise Exception('Login canceled! Did not accept host server\'s certificate.')

        elif item == SFTP.NEW_REMOTE_CERT_WARN:
            msg = _("Host's certificate changed! Proceed?\n\n")+fingerprints
            res = msg_box(msg, MB_OKCANCEL | MB_ICONWARNING)
            if res == ID_OK:
                server["remote_cert_fingerprint"] = sha1_fp
                self.save_options()
                show_log('Private key Auth', 'Accepted changed host\'s certificate')
                next(resgen) # continue login process
                return
            else:
                raise Exception('Login canceled! Did not accept remote host\'s changed certificate.')

    def retrieve_file(self, server, server_path, client_path):
        try:
            client_path.parent.mkdir(parents=True)
        except FileExistsError:
            pass

        def retr_callback(data):
            nonlocal progress
            nonlocal progress_prev
            progress += len(data)

            TEST_ESC_EACH_KBYTES = 50
            SMOOTH_SIZE_KBYTES = 30
            if (progress-progress_prev) // 1024 > TEST_ESC_EACH_KBYTES:
                msg_status(
                    _("Downloading '{}': {} Kbytes").format(
                        server_path.name,
                        # rounding by N kb: divide, then multiply
                        progress // 1024 // SMOOTH_SIZE_KBYTES * SMOOTH_SIZE_KBYTES,
                    ),
                    True
                )
                progress_prev = progress
                if app_proc(PROC_GET_ESCAPE, ''):
                    text = "Downloading of '{}' stopped".format(server_path.name)
                    msg_status(text)
                    raise Exception(text)

            fout.write(data)

        progress = 0
        progress_prev = 0
        app_proc(PROC_SET_ESCAPE, '0')
        with CommonClient(server) as client:
            self.login(client, server)
            with client_path.open(mode="wb") as fout:
                client.retrbinary("RETR " + str(server_path), retr_callback)

    def get_server_by_alias(self, alias):
        for server in self.options["servers"]:
            if server_alias(server) == alias:
                return server
        raise Exception("No server with alias '{}'".format(alias))

    def get_server_by_short_info(self, address, login):
        # print('Finding server:', address+'@'+login)
        for server in self.options["servers"]:
            key = (server_type(server) + "://" + server_address(server) + ":" + server_port(server),
                        server_login(server) )
            if key == (address, login):
                return server
        raise Exception("Server {}@{} has no full info".format(address, login))


    def get_location_by_index(self, index):
        path = []
        while not self.get_info(index).image == NODE_SERVER: # build path from tree nodes
            path.append(self.get_info(index).caption)
            index = tree_proc(self.tree, TREE_ITEM_GET_PROPS, index)['parent']
        path.reverse()
        server_path = PurePosixPath("/" + str.join("/", path))

        server = self.get_server_by_alias(self.get_info(index).caption)

        prefix = pathlib.Path(
            server_type(server),
            server_address(server),
            server_port(server)
            )
        client_path = (
            self.temp_dir_path / prefix /
            server_login(server) / server_path.relative_to("/")
        )
        return server, server_path, client_path

    def get_location_by_filename(self, filename):
        client_path = Path(filename)
        path = client_path.relative_to(self.temp_dir_path)
        address = "{}://{}:{}".format(*path.parts[:3])
        login = path.parts[3]
        server = self.get_server_by_short_info(address, login)
        virtual = PurePosixPath(*path.parts[:4])
        server_path = PurePosixPath("/") / path.relative_to(virtual)
        return server, server_path, client_path

    def node_remove_children(self, node_index):
        children = tree_proc(self.tree, TREE_ITEM_ENUM, node_index)
        for index, _x in (children or []):
            tree_proc(self.tree, TREE_ITEM_DELETE, index)

    def node_refresh(self, node_index):
        server, server_path, _x = self.get_location_by_index(node_index)
        try:
            with CommonClient(server) as client:
                self.login(client, server)
                path_list = sorted(
                    client.mlsd(server_path, server_use_list(server)),
                    key=lambda p: (p[1]["type"], p[0])
                )
        except Exception as ex:
            show_log(
                "Read dir: " + server_address(server) + str(server_path),
                str(ex)
            )
            raise

        for name, facts in path_list:
            if facts["type"] == "dir":
                NodeType = NODE_DIR
            elif facts["type"] == "file":
                NodeType = NODE_FILE
            else:
                continue
            tree_proc(
                self.tree,
                TREE_ITEM_ADD,
                node_index,
                -1,
                str(name),
                NodeType
            )
        tree_proc(self.tree, TREE_ITEM_UNFOLD_DEEP, node_index)

    def list_aliases(self):
        return [server_alias(s) for s in self.options["servers"]]

    def on_save(self, ed_self):
        if not self.inited:
            return
        filename = ed_self.get_filename()
        try:
            Path(filename).relative_to(self.temp_dir_path)
        except ValueError:
            return
        self.store_file(*self.get_location_by_filename(filename))

    def action_new_server(self, server=None):
        if server is None:
            server_info = dialog_server()
            if server_info is None:
                return

            # give alias
            alias = server_title(server_info)
            aliases = self.list_aliases()
            if alias in aliases:
                alias = next(al for al in server_alias_candidates(server_info)  if al not in aliases)
            server_info['alias'] = alias

            self.options["servers"].append(server_info)
            self.save_options()
            server = server_info
        caption = server_alias(server)
        tree_proc(self.tree, TREE_ITEM_ADD, 0, -1, caption, 0)

    def action_edit_server(self):
        server, *_x = self.get_location_by_index(self.selected)
        server_info = dialog_server(server)
        if server_info is None:
            return

        server_info['alias'] = server_alias(server)
        servers = self.options["servers"]
        i = servers.index(server)
        servers[i] = server_info
        server = server_info

        caption = server_alias(server)
        tree_proc(self.tree, TREE_ITEM_SET_TEXT, self.selected, 0, caption)
        self.save_options()

    def action_rename_server(self):
        # server, *_x = self.get_location_by_index(self.selected)
        # Mind the _(gettext) messages! (fm)
        server, *xx = self.get_location_by_index(self.selected)

        alias = server_alias(server)
        aliases = self.list_aliases()
        aliases.remove(alias)

        prev = None
        while True:
            prompt = _('Rename server: {}').format(alias)
            if prev:
                prompt += _('\nName taken: {}').format(prev)
            res = dlg_input(prompt,  prev or alias)

            if res is None:
                return
            if res == '': # reset to default
                res = next(al for al in server_alias_candidates(server)  if al not in aliases)
            if res not in aliases:
                server['alias'] = res
                break
            prev = res

        caption = server_alias(server)
        tree_proc(self.tree, TREE_ITEM_SET_TEXT, self.selected, 0, caption)
        self.save_options()


    def action_remove_server(self):
        res = msg_box(_("Do you really want to remove server?"), MB_YESNO+MB_ICONQUESTION)
        if res == ID_YES:
            server, *_x = self.get_location_by_index(self.selected)
            tree_proc(self.tree, TREE_ITEM_DELETE, self.selected)
            servers = self.options["servers"]
            servers.pop(servers.index(server))
            self.save_options()

    def action_go_to_dir(self):
        ret = dlg_input_ex(
            1,
            _("Go to directory"),
            _("Path:"),
            "/",
        )
        if ret:
            self.goto_server_path(ret[0])

    def action_go_to_file(self):
        ret = dlg_input_ex(
            1,
            _("Go to file"),
            _("Path:"),
            "/index.php",
        )
        if ret:
            self.go_to_file_(ret[0])

    def go_to_file_(self, path_, pinned_ = False):
        def get_filedir_(dat_):
            tmp = str(dat_).split("/")
            tmp.pop()
            return "/".join(tmp) + "/"

        def get_filename_(dat_):
            return (str(dat_).split("/"))[-1]

        self.goto_server_path(get_filedir_(path_))

        prop_list = tree_proc(self.tree, TREE_ITEM_ENUM, self.selected) or []
        for prop in prop_list:
            if prop[1] == get_filename_(path_):
                node = prop[0]
                tree_proc(self.tree, TREE_ITEM_SELECT, node)
                tree_proc(self.tree, TREE_ITEM_SHOW, node)
                break

        info = self.get_info(self.selected)
        if info.caption == get_filename_(path_):
            if info.image == NODE_FILE:
                self.action_open_file()
                self.save_to_history(False, pinned_)
        else:
            msg_status(_('Error: file not found on server!'))

    def get_server_alias_path(self):
        server, *xx = self.get_location_by_index(self.selected)

        return server_alias(server), xx

    def load_from_history(self):
        settings_dir = Path(app_path(APP_DIR_SETTINGS))
        self.history_filename = settings_dir / "cuda_ftp_history.json"

        data_load_ = ''
        if self.history_filename.exists():
            with self.history_filename.open(encoding="utf-8") as fin:
                data_load_ = json.load(fin)

        return data_load_

    def save_to_history(self, path_, pinned_ = False):
        alias_, filename__ = self.get_server_alias_path()
        filename_ = str(filename__[0])
        if (path_ and path_ != '/'):
            filename_ = path_
        if filename_ == '/':
            return

        datetime_ = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        data_2_ = {
            'filename': filename_,
            'datetime': datetime_,
            'pinned': pinned_,
        }
        data_1_ = {
            alias_: [
                data_2_
            ]
        }

        data_load_ = self.load_from_history()
        if data_load_:
            if data_load_.get(alias_) is not None:
                filenames = []
                for el in data_load_[alias_]:
                    filenames.append(el['filename'])
                if filename_ not in filenames:
                    data_load_[alias_].append(data_2_)
                else:
                    data_load_[alias_].pop(filenames.index(filename_))
                    data_load_[alias_].append(data_2_)
            else:
                d_ = data_load_.copy()
                d_.update(data_1_)
                data_load_ = d_
            data__ = data_load_
        else:
            data__ = data_1_

        with self.history_filename.open(mode="w", encoding="utf-8") as fout:
            json.dump(data__, fout, indent=2)

    def action_go_to_history(self):
        data_load_ = self.load_from_history()
        err = False
        if data_load_:
            items_ = ''
            items = []
            pinned_ = []
            alias_, filename__ = self.get_server_alias_path()
            if alias_ in data_load_:
                data_load_[alias_].reverse()
                index_ = 1
                for el in data_load_[alias_]:
                    if el.get('pinned', None) == True:
                        items_ = items_ + '[' + str(index_) + '] ' + el['filename'] + "\t" + el['datetime'] + "\n"
                        items.append(el['filename'])
                        pinned_.append(el['filename'])
                        index_ += 1
                for el in data_load_[alias_]:
                    if 'pinned' not in el or el['pinned'] == False:
                        items_ = items_ + el['filename'] + "\t" + el['datetime'] + "\n"
                        items.append(el['filename'])
                w_ = 600
                h_ = 600
                screen_sizes = app_proc(PROC_COORD_MONITOR, 0)
                if screen_sizes:
                    w_ = round(screen_sizes[2] / 3)
                    h_ = round(screen_sizes[3] / 3)
                res_ = dlg_menu(DMENU_LIST_ALT, items_, 0, _('History'), CLIP_LEFT, w_, h_)
                if res_ is not None:
                    if 'c' not in app_proc(PROC_GET_KEYSTATE, ''):
                        self.go_to_file_(items[res_], (items[res_] in pinned_))
                    else:
                        self.save_to_history(items[res_], (items[res_] not in pinned_))
                        self.action_go_to_history();
            else:
                err = True
        else:
            err = True

        if err:
            msg_box(_('No history found'), MB_OK)

    def goto_server_path(self, goto):
        path = PurePosixPath(goto)
        self.node_remove_children(self.selected)
        node = self.selected
        for name in filter(lambda n: n != "/", path.parts):
            node = tree_proc(
                self.tree,
                TREE_ITEM_ADD,
                node,
                -1,
                name,
                NODE_DIR
            )
        try:
            self.node_refresh(node)
        except:
            self.node_remove_children(self.selected)
            if SHOW_EX:
                raise
            else:
                return
        tree_proc(self.tree, TREE_ITEM_UNFOLD_DEEP, self.selected)
        tree_proc(self.tree, TREE_ITEM_SELECT, node)

        self.save_to_history(goto)

    def refresh_node(self, index):
        self.node_remove_children(index)
        try:
            self.node_refresh(index)
        except:
            if SHOW_EX:
                raise

    def action_refresh(self):
        # special case: refresh of server, with "init dir" set
        if self.is_selected_server():
            server, server_path, client_path = self.get_location_by_index(
                self.selected)
            goto = server_init_dir(server)
            if goto:
                self.goto_server_path(goto)
                return
        info = self.get_info(self.selected)
        if info.image == NODE_FILE:
            index = tree_proc(self.tree, TREE_ITEM_GET_PROPS, self.selected)['parent']
            self.refresh_node(index)
            self.select_node_parent(index)
        else:
            self.refresh_node(self.selected)

    def action_new_file(self):
        server, server_path, client_path = self.get_location_by_index(
            self.selected)
        file_info = dlg_input_ex(
            1,
            _("FTP new file"),
            _("File name:"), "",
        )
        if not file_info:
            return
        name = file_info[0]
        try:
            client_path.mkdir(parents=True)
        except FileExistsError:
            pass
        path = client_path / name
        path.touch()
        file_open(str(path), options='/nozip')
        server, server_path
        self.store_file(server, server_path / name, path)
        self.action_refresh()
        self.select_node(self.selected, str(path))
        self.save_to_history(str(server_path / name))

    def action_upload_here(self):
        server, server_path, client_path = self.get_location_by_index(self.selected)
        path = os.path.dirname(ed.get_filename())
        path = dlg_file(True, '', path, '')
        if path is None:
            return
        self.store_file(server, server_path / Path(os.path.basename(path)), Path(path))
        self.action_refresh()

    def remove_file(self, server, server_path, client_path):
        with CommonClient(server) as client:
            self.login(client, server)
            client.delete(str(server_path))

    def action_remove_file(self):
        res = msg_box(_("Do you really want to remove file?"), MB_YESNO+MB_ICONQUESTION)
        if res == ID_YES:
            try:
                self.remove_file(*self.get_location_by_index(self.selected))
                server, server_path, _x = self.get_location_by_index(self.selected)
                show_log("[×] Removed", server_address(server) + str(server_path))
                index = tree_proc(self.tree, TREE_ITEM_GET_PROPS, self.selected)['parent']
                self.refresh_node(index)
                self.select_node_parent(index)
            except Exception as ex:
                show_log("Remove file", str(ex))
                if SHOW_EX:
                    raise

    def action_new_dir(self):
        server, server_path, client_path = self.get_location_by_index(
            self.selected)
        dir_info = dlg_input_ex(
            1,
            _("FTP new directory"),
            _("Directory name:"), "",
        )
        if not dir_info:
            return
        name = dir_info[0]
        try:
            with CommonClient(server) as client:
                self.login(client, server)
                client.mkd(str(server_path / name))
        except Exception as ex:
            show_log("Create dir", str(ex))
            if SHOW_EX:
                raise
        self.refresh_node(self.selected)
        self.select_node(self.selected, str(server_path / name))
        self.save_to_history(str(server_path / name))

    def remove_directory_recursive(self, client, path):
        if app_proc(PROC_GET_ESCAPE, ""):
            raise Exception("Stopped by user")

        server, server_path, client_path = self.get_location_by_index(
            self.selected)

        for name, facts in tuple(client.mlsd(path, server_use_list(server))):
            if facts["type"] == "dir":
                msg_status(_("Removing ftp dir: ") + str(path / name), True)
                self.remove_directory_recursive(client, path / name)
            elif facts["type"] == "file":
                msg_status(_("Removing ftp file: ") + str(path / name), True)
                client.delete(str(path / name))
        msg_status(_("Removing ftp dir: ") + str(path), True)
        client.rmd(str(path))

    def action_remove_dir(self):
        app_proc(PROC_SET_ESCAPE, "0")
        server, server_path, _x = self.get_location_by_index(self.selected)
        res = msg_box(_("Do you really want to remove directory?"), MB_YESNO+MB_ICONQUESTION)
        if res == ID_YES:
            try:
                with CommonClient(server) as client:
                    self.login(client, server)
                    self.remove_directory_recursive(client, server_path)
                    show_log("[×] Removed", server_address(server) + str(server_path))
                    index = tree_proc(self.tree, TREE_ITEM_GET_PROPS, self.selected)['parent']
                    tree_proc(self.tree, TREE_ITEM_DELETE, self.selected)
                    self.refresh_node(index)
                    self.select_node_parent(index)
            except Exception as ex:
                show_log("Remove dir", str(ex))
                if SHOW_EX:
                    raise

    def action_open_file(self):
        path_info = server, server_path, client_path = \
            self.get_location_by_index(self.selected)
        try:
            self.retrieve_file(*path_info)
            show_log("[↓] Downloaded", server_address(server) + str(server_path))
            file_open(str(client_path), options='/nozip /nontext-view-hex')
        except Exception as ex:
            show_log("Download file", str(ex))
            if SHOW_EX:
                raise

    def action_get_properties(self):
        def convert_size(size_bytes):
            size_bytes = int(size_bytes)
            if size_bytes == 0:
                return "0b"
            size_name = ("b", "kB", "mB", "gB")
            i = int(math.floor(math.log(size_bytes, 1024)))
            p = math.pow(1024, i)
            s = round(size_bytes / p, 2)
            return str("%s %s" % (s, size_name[i]))

        def get_datetime(dat_):
            today_ = datetime.now().strftime("%d.%m.%Y")
            date_ = datetime.strptime(dat_, "%Y%m%d%H%M%S").strftime("%d.%m.%Y")
            if (date_ == today_):
                res_ = _('today ') + datetime.strptime(dat_, "%Y%m%d%H%M%S").strftime("%H:%M:%S")
            else:
                res_ = datetime.strptime(dat_, "%Y%m%d%H%M%S").strftime("%d.%m.%Y %H:%M:%S")
            return res_

        def output_file_info(dat_):
            res_ = ''
            keys_ = ["size", "modify", "unix.mode"]
            outs_ = []
            for key_ in keys_:
                if dat_.get(key_) is not None:
                    outs_.append(key_)
            for out_ in outs_:
                if (out_ == keys_[0]):
                    res_ += _('Size: ') + convert_size(dat_["size"]) + "\n\n"
                if (out_ == keys_[1]):
                    res_ += _('Modification: ') + get_datetime(dat_["modify"]) + "\n\n"
                if (out_ == keys_[2]):
                    res_ += _('Permissions: ')+ dat_["unix.mode"]
            return res_

        server, server_path, _x = self.get_location_by_index(self.selected)

        def get_filedir(dat_):
            tmp = str(dat_).split("/")
            tmp.pop()
            return "/".join(tmp) + "/"

        server_path_ = get_filedir(server_path)

        with CommonClient(server) as client:
            self.login(client, server)
            path_list = sorted(
                    client.mlsd(server_path_, server_use_list(server)),
                    key=lambda p: (p[1]["type"], p[0])
                )

        dat_ = ""
        for name, facts in path_list:
            name_ = str(server_path_ + name)
            if (name_ == str(server_path)):
                dat_ = facts

        msg_box(output_file_info(dat_), MB_OK+MB_ICONINFO)

    def action_copy_path(self):
        server, server_path, _x = self.get_location_by_index(self.selected)
        app_proc(PROC_SET_CLIP, server_path)

    def action_copy_link(self):
        server, server_path, _x = self.get_location_by_index(self.selected)
        alias, __x = self.get_server_alias_path()
        server_path_ = str(server_path)
        ph = '/public_html/'
        w = '/www/'
        paths = [w + alias, ph + alias, '/' + alias + w, '/' + alias + ph]
        for p in paths:
            if server_path_.startswith(p):
                server_path_ = server_path_.replace(p, '')
        link = (alias  + '/' + server_path_).replace(ph, '/').replace('//', '/')
        app_proc(PROC_SET_CLIP, link)
        msg_status(_("Link copied to clipboard: " + link), True)

    def action_download_file(self):
        server, server_path, _x = self.get_location_by_index(self.selected)
        alias, __x = self.get_server_alias_path()

        path_ = os.path.join(os.path.expanduser('~'), 'cudatext_ftp') + os.sep + alias + str(server_path)

        def get_filedir_(dat_):
            tmp = str(dat_).split(os.sep)
            tmp.pop()
            return os.sep.join(tmp) + os.sep
        dir_ = get_filedir_(path_)

        if (os.path.exists(dir_) == False):
            try:
                path__ = Path(dir_)
                path__.mkdir(parents=True)
            except OSError as err:
                msg_box("OS error: {0}".format(err), MB_OK)
                raise

        try:
            os.remove(path_)
        except OSError:
            pass

        self.retrieve_file(server, server_path, Path(path_))

        if os.path.exists(path_):
            msg_status(_("File downloaded to: ") + path_, True)
            show_log("[↓] Downloaded", server_address(server) + str(server_path))

    def action_backup_file(self):
        server, server_path, _x = self.get_location_by_index(self.selected)
        def get_filedir_(dat_):
            tmp = str(dat_).split(os.sep)
            tmp.pop()
            return os.sep.join(tmp) + os.sep
        def get_backup_filename_(dat_):
            filename, file_extension = os.path.splitext((str(dat_).split("/"))[-1])
            return filename + '.' + datetime.now().strftime("%y%m%d_%H%M%S") + file_extension
        res = dlg_input(_("Backup: "), get_backup_filename_(server_path))
        if res is None:
            return
        else:
            try:
                new_path_server = get_filedir_(server_path) + res
                self.retrieve_file(server, server_path, _x)
                new_path = get_filedir_(_x) + res
                os.rename(str(_x), str(new_path))
                self.store_file(server, Path(new_path_server), Path(new_path))
                show_log("[!] Backup", server_address(server) + str(server_path) + " to " + new_path_server)
                index = tree_proc(self.tree, TREE_ITEM_GET_PROPS, self.selected)['parent']
                self.refresh_node(index)
                self.select_node(index, new_path_server)
            except Exception as ex:
                show_log("Backup file", str(ex))
                if SHOW_EX:
                    raise

    def rename_file_dir(self, server, server_path, client_path, new_name):
        with CommonClient(server) as client:
            self.login(client, server)
            client.rename(str(server_path), str(new_name))

    def action_rename_file_dir(self):
        server, server_path, _x = self.get_location_by_index(self.selected)
        def get_filedir_(dat_):
            tmp = str(dat_).split(os.sep)
            tmp.pop()
            return os.sep.join(tmp) + os.sep
        def get_filename_(dat_):
            return (str(dat_).split("/"))[-1]
        res = dlg_input(_("Rename: "), get_filename_(server_path))
        if res is None:
            return
        else:
            try:
                newname = get_filedir_(server_path) + res
                self.rename_file_dir(*self.get_location_by_index(self.selected), newname)
                show_log("[!] Renamed", server_address(server) + str(server_path))
                index = tree_proc(self.tree, TREE_ITEM_GET_PROPS, self.selected)['parent']
                self.refresh_node(index)
                self.select_node(index, newname)
            except Exception as ex:
                show_log("Rename file/dir", str(ex))
                if SHOW_EX:
                    raise

    def select_node(self, parent, path):
        prop_list = tree_proc(self.tree, TREE_ITEM_ENUM, parent) or []
        name = (path.split(os.sep))[-1]
        for prop in prop_list:
            if prop[1] == name:
                tree_proc(self.tree, TREE_ITEM_SELECT, prop[0])
                tree_proc(self.tree, TREE_ITEM_SHOW, prop[0])
                break

    def select_node_parent(self, parent):
        tree_proc(self.tree, TREE_ITEM_SELECT, parent)
        tree_proc(self.tree, TREE_ITEM_SHOW, parent)

    def save_options(self):
        with self.options_filename.open(mode="w") as fout:
            json.dump(self.options, fout, indent=2)

    def is_selected_server(self):
        info = self.get_info(self.selected)
        return info.image == NODE_SERVER

    def tree_on_menu(self, id_dlg, id_ctl, data='', info=''):
        self.generate_context_menu()
        menu_proc(self.h_menu, MENU_SHOW, command='')

    def tree_on_click_dbl(self, id_dlg, id_ctl, data='', info=''):
        info = self.get_info(self.selected)
        if info.image in (NODE_SERVER, NODE_DIR):
            self.action_refresh()
        elif info.image == NODE_FILE:
            self.action_open_file()
            self.save_to_history(False)

    def form_on_key(self, id_dlg, id_ctl, data='', info=''):
        #Space, Enter or F4 pressed
        if id_ctl in [VK_SPACE, VK_ENTER, VK_F4] and data == '':
            self.tree_on_click_dbl(id_dlg, 0, '', '')
        #Del pressed
        elif id_ctl == VK_DELETE:
            info = self.get_info(self.selected)
            if info.image == NODE_FILE:
                self.action_remove_file()
            elif info.image == NODE_DIR:
                self.action_remove_dir()
        #F5 or Ctrl+R pressed
        elif (id_ctl == VK_F5) or (data == 'c' and id_ctl == 0x52):
            self.action_refresh()
            return False
        #F2 pressed
        elif id_ctl == VK_F2:
            info = self.get_info(self.selected)
            if (info.image == NODE_FILE or info.image == NODE_DIR):
                self.action_rename_file_dir()
            if info.image == NODE_SERVER:
                self.action_rename_server()
