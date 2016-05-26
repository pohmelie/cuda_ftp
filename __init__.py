import collections
import contextlib
import pathlib
import json
import tempfile
import enum
import itertools
from ftplib import FTP, error_perm

from cudatext import *
import cudatext_cmd


@contextlib.contextmanager
def FTPClient(server):

    client = FTP()
    if ":" in server.address:

        host, port = str.split(server.address, ":")

    else:

        host, port = server.address, 0

    client.connect(host, int(port))
    yield client
    client.quit()


class Node(enum.IntEnum):

    SERVER = 0
    DIRECTORY = 1
    FILE = 2

    def __init__(self, index):

        filenames = (
            "cuda-ftp-icon-server.png",
            "cuda-ftp-icon-directory.png",
            "cuda-ftp-icon-file.png",
        )
        self.filename = pathlib.Path(filenames[index])


NodeInfo = collections.namedtuple("NodeInfo", "caption index image level")
Server = collections.namedtuple("Server", "address login password")


class Command:

    title = "Ftp"
    actions = {
        None: (
            "New server",
        ),
        Node.SERVER: (
            "New server",
            "Remove server",
            "New file",
            "New dir",
            "Refresh",
        ),
        Node.DIRECTORY: (
            "New file",
            "New dir",
            "Remove dir",
            "Refresh",
        ),
        Node.FILE: (
            "Open file",
            "Remove file",
        ),
    }

    def toggle(self, visible=True):

        ed.cmd(cudatext_cmd.cmd_ShowSidePanelAsIs)
        app_proc(PROC_SIDEPANEL_ADD, self.title + ",-1,tree")

        if visible:

            app_proc(PROC_SIDEPANEL_ACTIVATE, self.title)

        self.tree = app_proc(PROC_SIDEPANEL_GET_CONTROL, self.title)
        tree_proc(self.tree, TREE_ITEM_DELETE, 0)

        base = pathlib.Path(__file__).parent
        for node in Node:

            path = base / node.filename
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

            client.login(server.login, server.password)
            try:

                client.mkd(str(server_path.parent))

            except error_perm as e:

                pass

            with client_path.open(mode="rb") as fin:

                client.storbinary("STOR " + str(server_path), fin)

    def retrieve_file(self, server, server_path, client_path):

        try:

            client_path.parent.mkdir(parents=True)

        except FileExistsError:

            pass

        with FTPClient(server) as client:

            client.login(server.login, server.password)
            with client_path.open(mode="wb") as fout:

                client.retrbinary("RETR " + str(server_path), fout.write)

    def get_server_by_short_info(self, address, login):

        for server in itertools.starmap(Server, self.options["servers"]):

            if (server.address, server.login) == (address, login):

                return server

        raise Exception(
            str.format(
                "Server {}@{} have no full info",
                address,
                login,
            )
        )

    def get_location_by_index(self, index):

        path = []
        while not self.get_info(index).image == Node.SERVER:

            path.append(self.get_info(index).caption)
            index = tree_proc(self.tree, TREE_ITEM_GET_PARENT, index)

        path.reverse()
        server_path = pathlib.PurePosixPath("/" + str.join("/", path))

        short_info = str.split(self.get_info(index).caption, "@")
        server = self.get_server_by_short_info(*short_info)
        p = server_path.relative_to("/")
        client_path = self.temp_dir_path / server.address / server.login / p
        return server, server_path, client_path

    def get_location_by_filename(self, filename):

        client_path = pathlib.Path(filename)
        path = client_path.relative_to(self.temp_dir_path)
        server = self.get_server_by_short_info(*path.parts[:2])
        virtual = pathlib.PurePosixPath(server.address) / server.login
        server_path = pathlib.PurePosixPath("/") / path.relative_to(virtual)
        return server, server_path, client_path

    def node_remove_children(self, node_index):

        children = tree_proc(self.tree, TREE_ITEM_ENUM, node_index)
        for index, _ in (children or []):

            tree_proc(self.tree, TREE_ITEM_DELETE, index)

    def node_refresh(self, node_index):

        server, server_path, _ = self.get_location_by_index(node_index)
        with FTPClient(server) as client:

            client.login(server.login, server.password)
            path_list = sorted(
                client.mlsd(server_path),
                key=lambda p: (p[1]["type"], p[0])
            )

        for name, facts in path_list:

            if facts["type"] == "dir":

                NodeType = Node.DIRECTORY

            elif facts["type"] == "file":

                NodeType = Node.FILE

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

    def on_start(self, ed_self):

        self.toggle(False)
        self.options = {"servers": []}
        settings_dir = pathlib.Path(app_path(APP_DIR_SETTINGS))
        self.options_filename = settings_dir / "cuda_ftp.json"
        if self.options_filename.exists():

            with self.options_filename.open() as fin:

                self.options = json.load(fin)

        for server in itertools.starmap(Server, self.options["servers"]):

            self.action_new_server(server)

        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir_path = pathlib.Path(self.temp_dir.name)

    def on_save(self, ed_self):

        self.store_file(*self.get_location_by_filename(ed_self.get_filename()))

    def on_panel(self, ed_self, id_control, id_event):

        if id_event == "on_sel":

            self.generate_context_menu()

        elif id_event == "on_dbl_click":

            info = self.get_info(self.selected)
            if info.image in (Node.SERVER, Node.DIRECTORY):

                self.action_refresh()

            elif info.image == Node.FILE:

                self.action_open_file()

    def action_new_server(self, server=None):

        if server is None:

            server_info = dlg_input_ex(
                3,
                "FTP server info",
                "Address:", "",
                "Login:", "anonymous",
                "Password:", "anon@",
            )
            if server_info is None:

                return

            self.options["servers"].append(server_info)
            self.save_options()
            server = Server(*server_info)

        caption = str.format("{}@{}", server.address, server.login)
        tree_proc(self.tree, TREE_ITEM_ADD, 0, -1, caption, 0)

    def action_remove_server(self):

        server, *_ = self.get_location_by_index(self.selected)
        tree_proc(self.tree, TREE_ITEM_DELETE, self.selected)
        servers = self.options["servers"]
        servers.pop(servers.index(list(ftp)))
        self.save_options()

    def refresh_node(self, index):

        self.node_remove_children(index)
        self.node_refresh(index)

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

            client.login(server.login, server.password)
            client.delete(str(server_path))

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

            client.login(server.login, server.password)
            client.mkd(str(server_path / name))

        self.refresh_node(self.selected)

    def remove_directory_recursive(self, client, path):

        for name, facts in tuple(client.mlsd(path)):

            if facts["type"] == "dir":

                self.remove_directory_recursive(client, path / name)

            elif facts["type"] == "file":

                client.delete(str(path / name))

        client.rmd(str(path))

    def action_remove_dir(self):

        server, server_path, _ = self.get_location_by_index(self.selected)
        with FTPClient(server) as client:

            client.login(server.login, server.password)
            self.remove_directory_recursive(client, server_path)

        tree_proc(self.tree, TREE_ITEM_DELETE, self.selected)

    def action_open_file(self):

        path_info = *_, client_path = self.get_location_by_index(self.selected)
        self.retrieve_file(*path_info)
        file_open(str(client_path))

    def save_options(self):

        with self.options_filename.open(mode="w") as fout:

            json.dump(self.options, fout)
