import collections
import contextlib
import json
import tempfile
import itertools
from ftplib import FTP, error_perm
from .pathlib import Path, PurePosixPath
from datetime import datetime

from cudatext import *
import cudatext_cmd


def server_address(server):
    return server.get('address', '')
def server_login(server):
    return server.get('login', '')
def server_password(server):
    return server.get('password', '')

@contextlib.contextmanager
def FTPClient(server):

    client = FTP()
    adr = server_address(server)
    if ":" in adr:

        host, port = str.split(adr, ":")

    else:

        host, port = adr, 0

    client.connect(host, int(port))
    yield client
    client.quit()


def show_log(str1, str2):
    time_fmt = '[%H:%M] '
    time_str = datetime.now().strftime(time_fmt)
    ed.cmd(cudatext_cmd.cmd_ShowPanelOutput)
    app_log(LOG_SET_PANEL, LOG_PANEL_OUTPUT)
    app_log(LOG_ADD, time_str + str1 + ': ' + str2)
    lines = app_log(LOG_GET_LINES, '').split('\n')
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
            "New server",
            "Edit server",
            "Remove server",
            "New file",
            "New dir",
            "Refresh",
        ),
        NODE_DIR: (
            "New file",
            "New dir",
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

            action_name = str.lower("action_" + str.replace(name, " ", "_"))
            desc = str.format(
                "{};cuda_ftp,{};{};-1",
                side_name,
                action_name,
                name,
            )
            app_proc(PROC_MENU_ADD, desc)

    def store_file(self, server, server_path, client_path):

        with FTPClient(server) as client:

            client.login(server_login(server), server_password(server))
            try:

                client.mkd(str(server_path.parent))

            except error_perm as e:

                pass

            with client_path.open(mode="rb") as fin:

                try:
                    client.storbinary("STOR " + str(server_path), fin)
                except Exception as ex:
                    show_log('Upload file', str(ex))
                    

    def retrieve_file(self, server, server_path, client_path):

        try:

            client_path.parent.mkdir(parents=True)

        except FileExistsError:

            pass

        with FTPClient(server) as client:

            client.login(server_login(server), server_password(server))
            with client_path.open(mode="wb") as fout:

                try:    
                    client.retrbinary("RETR " + str(server_path), fout.write)
                except Exception as ex:
                    show_log('Download file', str(ex))

    def get_server_by_short_info(self, address, login):

        for server in self.options["servers"]:

            if (server_address(server), server_login(server)) == (address, login):

                return server

        raise Exception(
            str.format(
                "Server {}@{} has no full info",
                address,
                login,
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
        p = server_path.relative_to("/")
        client_path = self.temp_dir_path / server_address(server) / server_login(server) / p
        return server, server_path, client_path

    def get_location_by_filename(self, filename):

        client_path = Path(filename)
        path = client_path.relative_to(self.temp_dir_path)
        server = self.get_server_by_short_info(*path.parts[:2])
        virtual = PurePosixPath(server_address(server)) / server_login(server)
        server_path = PurePosixPath("/") / path.relative_to(virtual)
        return server, server_path, client_path

    def node_remove_children(self, node_index):

        children = tree_proc(self.tree, TREE_ITEM_ENUM, node_index)
        for index, _ in (children or []):

            tree_proc(self.tree, TREE_ITEM_DELETE, index)

    def node_refresh(self, node_index):

        server, server_path, _ = self.get_location_by_index(node_index)
        with FTPClient(server) as client:

            client.login(server_login(server), server_password(server))
            path_list = sorted(
                client.mlsd(server_path),
                key=lambda p: (p[1]["type"], p[0])
            )

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

    def get_server_info(self, init_server=None):

        res = dlg_input_ex(
            3,
            "FTP server info",
            "Address (e.g. ftp.site.com:21):", (server_address(init_server) if init_server else ''),
            "Login:", (server_login(init_server) if init_server else 'anonymous'),
            "Password:", (server_password(init_server) if init_server else 'user@aol.com'),
        )
        if res is not None:
            return dict(zip(("address", "login", "password"), res))

    def action_new_server(self, server=None):

        if server is None:

            server_info = self.get_server_info()
            if server_info is None:

                return

            self.options["servers"].append(server_info)
            self.save_options()
            server = server_info

        caption = str.format("{}@{}", server_address(server), server_login(server))
        tree_proc(self.tree, TREE_ITEM_ADD, 0, -1, caption, 0)

    def action_edit_server(self):

        server, *_ = self.get_location_by_index(self.selected)
        server_info = self.get_server_info(server)
        if server_info is None:

            return

        servers = self.options["servers"]
        i = servers.index(server)
        servers[i] = server_info
        server = server_info
        caption = str.format("{}@{}", server_address(server), server_login(server))
        tree_proc(self.tree, TREE_ITEM_SET_TEXT, self.selected, 0, caption)
        self.save_options()

    def action_remove_server(self):

        server, *_ = self.get_location_by_index(self.selected)
        tree_proc(self.tree, TREE_ITEM_DELETE, self.selected)
        servers = self.options["servers"]
        servers.pop(servers.index(server))
        self.save_options()

    def refresh_node(self, index):

        self.node_remove_children(index)
        try:
            self.node_refresh(index)
        except Exception as ex:
            show_log('Refresh node', str(ex))

    def action_refresh(self):

        self.refresh_node(self.selected)

    def action_new_file(self):

        server, server_path, client_path = self.get_location_by_index(
            self.selected)
        file_info = dlg_input_ex(
            1,
            "FTP new file",
            "Filename:", "",
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

        with FTPClient(server) as client:

            try:    
                client.login(server_login(server), server_password(server))
                client.delete(str(server_path))
            except Exception as ex:
                show_log('Remove file', str(ex))

    def action_remove_file(self):

        self.remove_file(*self.get_location_by_index(self.selected))
        index = tree_proc(self.tree, TREE_ITEM_GET_PARENT, self.selected)
        self.refresh_node(index)

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
        with FTPClient(server) as client:

            try:
                client.login(server_login(server), server_password(server))
                client.mkd(str(server_path / name))
            except Exception as ex:
                show_log('Create dir', str(ex))

        self.refresh_node(self.selected)

    def remove_directory_recursive(self, client, path):

        if app_proc(PROC_GET_ESCAPE, ''):
            return False

        for name, facts in tuple(client.mlsd(path)):

            if facts["type"] == "dir":

                msg_status('Removing ftp dir: '+str(path / name), True)
                self.remove_directory_recursive(client, path / name)

            elif facts["type"] == "file":

                msg_status('Removing ftp file: '+str(path / name), True)
                client.delete(str(path / name))

        client.rmd(str(path))
            

    def action_remove_dir(self):

        app_proc(PROC_SET_ESCAPE, '0')

        server, server_path, _ = self.get_location_by_index(self.selected)
        with FTPClient(server) as client:

            try:
                client.login(server_login(server), server_password(server))
                if self.remove_directory_recursive(client, server_path) == False:
                    return
                tree_proc(self.tree, TREE_ITEM_DELETE, self.selected)
            except Exception as ex:
                show_log('Remove dir', str(ex))


    def action_open_file(self):

        path_info = *_, client_path = self.get_location_by_index(self.selected)
        self.retrieve_file(*path_info)
        file_open(str(client_path))

    def save_options(self):

        with self.options_filename.open(mode="w") as fout:

            fout.write(json.dumps(self.options, indent=2))
