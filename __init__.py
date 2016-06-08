import collections
import contextlib
import json
import tempfile
import socket
import stat
from ftplib import FTP, error_perm
from .pathlib import Path, PurePosixPath
from datetime import datetime

try:

    import paramiko

except ImportError:

    paramiko = None

from cudatext import *
import cudatext_cmd


# Show ftp exceptions in Console panel (download/upload/etc)
# Not good since errors shown in FTP Log panel anyway
SHOW_EX = False


def server_address(server):

    return server.get("address", "")


def server_login(server):

    return server.get("login", "")


def server_password(server):

    return server.get("password", "")


def server_init_dir(server):

    return server.get("init_dir", "")


def server_timeout(server):

    s = server.get("timeout", "")
    try:
        n = int(s)
        return s
    except:
        return '30'


def server_port(server):

    s = server.get("port", "")
    try:
        n = int(s)
        return s
    except:
        if server_type(server) == 'ftp':
            return '21'
        else:
            return '22'


def server_type(server):

    s = server.get("type", "")
    if not s in ('ftp', 'sftp'):
        s = 'ftp'
    return s


def server_list_caption(server):

    return str.format("{}://{}:{}@{}", 
        server_type(server), 
        server_address(server), 
        server_port(server), 
        server_login(server),
    )


def dialog_server(init_server=None):
    """ 
    Must give dict, which can be parsed by server_nnnnn(), or None
    """

    _typ = server_type(init_server) if init_server else "ftp"
    _adr = server_address(init_server) if init_server else ""
    _prt = server_port(init_server) if init_server else ""
    _log = server_login(init_server) if init_server else "anonymous"
    _pwd = server_password(init_server) if init_server else "user@aol.com"
    _dir = server_init_dir(init_server) if init_server else ""
    _tim = server_timeout(init_server) if init_server else "30"

    res = dlg_input_ex(
        7,
        "FTP server info",
        "Type (ftp, sftp):", _typ,
        "Host (e.g. ftp.site.com):", _adr,
        "Port (e.g. 21):", _prt,
        "Login:", _log,
        "Password:", _pwd,
        "Initial remote dir:", _dir,
        "Timeout (seconds):", _tim,
    )

    if not res:

        return

    data = dict(zip(("type", "address", "port", "login", "password", "init_dir", "timeout"), res))
    return data


class SFTP:

    def connect(self, address, port, timeout=None):

        self.sock = socket.create_connection((address, port), timeout=timeout)
        self.transport = paramiko.transport.Transport(self.sock)

    def login(self, username, password):

        self.transport.connect(None, username, password)
        self.sftp = self.transport.open_sftp_client()

    def quit(self):

        self.sftp.close()
        self.transport.close()

    def mlsd(self, path):

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
                "Please install 'Paramiko' library for SFTP support",
                MB_OK | MB_ICONERROR,
            )

        client = SFTP()

    elif schema == "ftp":

        client = FTP()

    else:

        raise Exception(str.format("Unknown server type: '{}'", schema))

    client.connect(host, int(port), timeout=int(timeout))
    yield client
    client.quit()


def show_log(str1, str2):

    title = "FTP Log"
    time_fmt = "[%H:%M] "
    time_str = datetime.now().strftime(time_fmt)
    ed.cmd(cudatext_cmd.cmd_ShowPanelOutput)
    app_log(LOG_PANEL_ADD, title)
    app_log(LOG_PANEL_FOCUS, title)
    app_log(LOG_SET_PANEL, title)
    app_log(LOG_ADD, time_str + str1 + ": " + str2)
    lines = app_log(LOG_GET_LINES, "").split("\n")
    app_log(LOG_SET_LINEINDEX, str(len(lines)-1))


NODE_SERVER = 0
NODE_DIR = 1
NODE_FILE = 2

icon_names = {
    NODE_SERVER: "cuda-ftp-icon-server.png",
    NODE_DIR: "cuda-ftp-icon-directory.png",
    NODE_FILE: "cuda-ftp-icon-file.png",
}


NodeInfo = collections.namedtuple("NodeInfo", "caption index image level")


class Command:

    inited = False
    title = "FTP"
    actions = {
        None: (
            "New server",
        ),
        NODE_SERVER: (
            "New server...",
            "Edit server...",
            "Remove server",
            "Go to...",
            "New file...",
            "New dir...",
            "Refresh",
        ),
        NODE_DIR: (
            "New file...",
            "New dir...",
            "Remove dir",
            "Refresh",
        ),
        NODE_FILE: (
            "Open file",
            "Remove file",
        ),
    }

    def init_options(self):

        self.options = {"servers": []}
        settings_dir = Path(app_path(APP_DIR_SETTINGS))
        self.options_filename = settings_dir / "cuda_ftp.json"

        if self.options_filename.exists():

            with self.options_filename.open() as fin:

                self.options = json.load(fin)

        for server in self.options["servers"]:

            self.action_new_server(server)

        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir_path = Path(self.temp_dir.name)

    def init_panel(self):

        ed.cmd(cudatext_cmd.cmd_ShowSidePanelAsIs)
        app_proc(PROC_SIDEPANEL_ADD, self.title + ",-1,tree")

        self.tree = app_proc(PROC_SIDEPANEL_GET_CONTROL, self.title)
        tree_proc(self.tree, TREE_ITEM_DELETE, 0)

    def show_panel(self, visible=True):

        self.inited = True
        self.init_panel()
        self.init_options()

        if visible:

            app_proc(PROC_SIDEPANEL_ACTIVATE, self.title)

        base = Path(__file__).parent
        for n in (NODE_SERVER, NODE_DIR, NODE_FILE):

            path = base / icon_names[n]
            tree_proc(self.tree, TREE_ICON_ADD, 0, 0, str(path))

        self.generate_context_menu()

    @property
    def selected(self):

        return tree_proc(self.tree, TREE_ITEM_GET_SELECTED)

    def get_info(self, index):

        return NodeInfo(*tree_proc(self.tree, TREE_ITEM_GET_PROP, index))

    def generate_context_menu(self):

        side_name = "side:" + self.title
        app_proc(PROC_MENU_CLEAR, side_name)
        if self.selected is not None:

            i = self.get_info(self.selected).image

        else:

            i = None

        for name in self.actions[i]:

            action_name = name.lower().replace(" ", "_").rstrip(".")
            desc = str.format(
                "{};cuda_ftp,{};{};-1",
                side_name,
                "action_" + action_name,
                name,
            )
            app_proc(PROC_MENU_ADD, desc)

    def store_file(self, server, server_path, client_path):

        try:

            with CommonClient(server) as client:

                client.login(server_login(server), server_password(server))
                try:

                    client.mkd(str(server_path.parent))

                except error_perm:

                    pass

                with client_path.open(mode="rb") as fin:

                    client.storbinary("STOR " + str(server_path), fin)

            show_log("Uploaded", server_address(server) + str(server_path))

        except Exception as ex:

            show_log("Upload file", str(ex))
            if SHOW_EX:
                raise

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
                    str.format(
                        "Downloading '{}': {} Kbytes",
                        server_path.name,
                        # rounding by N kb: divide, then multiply
                        progress // 1024 // SMOOTH_SIZE_KBYTES * SMOOTH_SIZE_KBYTES,
                    ),
                    True
                )

                progress_prev = progress
                if app_proc(PROC_GET_ESCAPE, ''):

                    text = str.format(
                        "Downloading of '{}' stopped",
                        server_path.name
                    )
                    msg_status(text)
                    raise Exception(text)

            fout.write(data)

        progress = 0
        progress_prev = 0
        app_proc(PROC_SET_ESCAPE, '0')

        with CommonClient(server) as client:

            client.login(server_login(server), server_password(server))
            with client_path.open(mode="wb") as fout:

                client.retrbinary("RETR " + str(server_path), retr_callback)

    def get_server_by_short_info(self, address, login):

        #print('Finding server:', address+'@'+login)

        for server in self.options["servers"]:

            key = server_type(server) + "://" + server_address(server) + ":" + server_port(server), server_login(server)
            if key == (address, login):

                return server

        raise Exception(
            str.format(
                "Server {}@{} has no full info",
                address,
                login
            )
        )

    def get_location_by_index(self, index):

        path = []
        while not self.get_info(index).image == NODE_SERVER:

            path.append(self.get_info(index).caption)
            index = tree_proc(self.tree, TREE_ITEM_GET_PARENT, index)

        path.reverse()
        server_path = PurePosixPath("/" + str.join("/", path))

        short_info = str.split(self.get_info(index).caption, "@")
        server = self.get_server_by_short_info(*short_info)
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
        address = str.format("{}://{}:{}", *path.parts[:3])
        login = path.parts[3]
        server = self.get_server_by_short_info(address, login)
        virtual = PurePosixPath(*path.parts[:4])
        server_path = PurePosixPath("/") / path.relative_to(virtual)
        return server, server_path, client_path

    def node_remove_children(self, node_index):

        children = tree_proc(self.tree, TREE_ITEM_ENUM, node_index)
        for index, _ in (children or []):

            tree_proc(self.tree, TREE_ITEM_DELETE, index)

    def node_refresh(self, node_index):

        server, server_path, _ = self.get_location_by_index(node_index)
        try:

            with CommonClient(server) as client:

                client.login(server_login(server), server_password(server))
                path_list = sorted(
                    client.mlsd(server_path),
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
                name,
                NodeType
            )

        tree_proc(self.tree, TREE_ITEM_UNFOLD_DEEP, node_index)

    def on_save(self, ed_self):

        if not self.inited:

            return

        filename = ed_self.get_filename()
        try:

            Path(filename).relative_to(self.temp_dir_path)

        except ValueError:

            return

        self.store_file(*self.get_location_by_filename(filename))

    def on_panel(self, ed_self, id_control, id_event):

        if not self.inited or id_control != self.tree:

            return

        if id_event == "on_sel":

            self.generate_context_menu()

        elif id_event == "on_dbl_click":

            info = self.get_info(self.selected)
            if info.image in (NODE_SERVER, NODE_DIR):

                self.action_refresh()

            elif info.image == NODE_FILE:

                self.action_open_file()

    def action_new_server(self, server=None):

        if server is None:

            server_info = dialog_server()
            if server_info is None:

                return

            self.options["servers"].append(server_info)
            self.save_options()
            server = server_info

        caption = server_list_caption(server)
        tree_proc(self.tree, TREE_ITEM_ADD, 0, -1, caption, 0)

    def action_edit_server(self):

        server, *_ = self.get_location_by_index(self.selected)
        server_info = dialog_server(server)
        if server_info is None:

            return

        servers = self.options["servers"]
        i = servers.index(server)
        servers[i] = server_info
        server = server_info
        caption = server_list_caption(server)
        tree_proc(self.tree, TREE_ITEM_SET_TEXT, self.selected, 0, caption)
        self.save_options()

    def action_remove_server(self):

        server, *_ = self.get_location_by_index(self.selected)
        tree_proc(self.tree, TREE_ITEM_DELETE, self.selected)
        servers = self.options["servers"]
        servers.pop(servers.index(server))
        self.save_options()

    def action_go_to(self):

        ret = dlg_input_ex(
            1,
            "Go to path",
            "Path:", "/",
        )

        if ret:

            self.goto_server_path(ret[0])

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

        self.refresh_node(self.selected)

    def action_new_file(self):

        server, server_path, client_path = self.get_location_by_index(
            self.selected)
        file_info = dlg_input_ex(
            1,
            "FTP new file",
            "File name:", "",
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
        file_open(str(path))
        server, server_path
        self.store_file(server, server_path / name, path)
        self.action_refresh()

    def remove_file(self, server, server_path, client_path):

        with CommonClient(server) as client:

            client.login(server_login(server), server_password(server))
            client.delete(str(server_path))

    def action_remove_file(self):

        try:

            self.remove_file(*self.get_location_by_index(self.selected))
            index = tree_proc(self.tree, TREE_ITEM_GET_PARENT, self.selected)
            self.refresh_node(index)

        except Exception as ex:

            show_log("Remove file", str(ex))
            if SHOW_EX:
                raise

    def action_new_dir(self):

        server, server_path, client_path = self.get_location_by_index(
            self.selected)
        dir_info = dlg_input_ex(
            1,
            "FTP new directory",
            "Directory name:", "",
        )
        if not dir_info:

            return

        name = dir_info[0]
        try:

            with CommonClient(server) as client:

                client.login(server_login(server), server_password(server))
                client.mkd(str(server_path / name))

        except Exception as ex:

            show_log("Create dir", str(ex))
            if SHOW_EX:
                raise

        self.refresh_node(self.selected)

    def remove_directory_recursive(self, client, path):

        if app_proc(PROC_GET_ESCAPE, ""):

            raise Exception("Stopped by user")

        for name, facts in tuple(client.mlsd(path)):

            if facts["type"] == "dir":

                msg_status("Removing ftp dir: " + str(path / name), True)
                self.remove_directory_recursive(client, path / name)

            elif facts["type"] == "file":

                msg_status("Removing ftp file: " + str(path / name), True)
                client.delete(str(path / name))

        msg_status("Removing ftp dir: " + str(path), True)
        client.rmd(str(path))

    def action_remove_dir(self):

        app_proc(PROC_SET_ESCAPE, "0")
        server, server_path, _ = self.get_location_by_index(self.selected)
        try:

            with CommonClient(server) as client:

                client.login(server_login(server), server_password(server))
                self.remove_directory_recursive(client, server_path)
                tree_proc(self.tree, TREE_ITEM_DELETE, self.selected)

        except Exception as ex:

            show_log("Remove dir", str(ex))
            if SHOW_EX:
                raise

    def action_open_file(self):

        path_info = server, server_path, client_path = \
            self.get_location_by_index(self.selected)
        try:

            self.retrieve_file(*path_info)
            show_log("Downloaded", server_address(server) + str(server_path))
            file_open(str(client_path))

        except Exception as ex:

            show_log("Download file", str(ex))
            if SHOW_EX:
                raise

    def save_options(self):

        with self.options_filename.open(mode="w") as fout:

            json.dump(self.options, fout, indent=2)

    def is_selected_server(self):
        info = self.get_info(self.selected)
        return info.image == NODE_SERVER
