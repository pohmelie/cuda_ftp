Plugin for CudaText.
Allows to manage remote FTP/SFTP files and directories.
Plugin shows FTP panel in the side panel, with context menu.
Context menu has commands:

Empty list:
 - new server
For servers:
 - new server
 - edit server
 - rename server
 - go to (change ftp directory)
 - new file (creates file in initial dir)
 - new dir (creates dir in initial dir)
 - refresh (re-reads initial dir)
 - remove server
For dirs (after opening server by double-clicking or "refresh"):
 - new file
 - new dir
 - remove dir
 - refresh (re-reads dir)
For files:
 - open file (download and open in editor)
 - remove file
 - opening history (ctrl+enter - pin/unpin of path)

General notes
-------------

- File, which was downloaded and edited, will be uploaded, when "Save" command runs.
- Config file is "[Cudatext]/settings/cuda_ftp.json"
- No permanent connection to server is kept. Each request (read dir, download, upload...)
  makes new connection, then closes the connection.

- Plugin supports several items for a single server. For example, work with SourceForge:
  you create N items for N projects, with different "initial dir" in each item.
  When you create few items for a single server, plugin adds "number suffix" to the caption.

- You can rename server items, by command "Rename" in the context menu.
  If you clear the custom name later, plugin will show default item caption.

Public key authentication
-------------------------

- Private key must be in OpenSSH format. PuTTYgen keys (.ppk) cen be converted to
  supported format by PuTTYgen itself.
- Server certificate's fingerprint is saved and you will be warned if it changes.
- Passphrase for a private key is never saved to disk, so after CudaText restart
  you will be prompted for it again.

SFTP support
------------
Read separate text-file about SFTP support.
For SFTP, Paramiko lib must be installed (on Linux and macOS).

About
-----
Authors:
  Nikita Melentev, https://github.com/pohmelie/
  Alexey Torgashin (CudaText)
  Shovel, https://github.com/halfbrained/
  Ildar Khasanshin, https://github.com/ildarkhasanshin
License: MIT
