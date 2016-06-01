Plugin for CudaText.
Allows to manage remote FTP files and directories.
Plugin shows FTP panel in side panel, with context menu.
Context menu items:

Empty list:
 - new server
For servers:
 - new server
 - edit server
 - remove server
 - new file (creates file in initial dir)
 - new dir (creates dir in initial dir)
 - refresh (re-reads initial dir)
For dirs (after opening server by double-clicking or "refresh"):
 - new file
 - new dir
 - remove dir
 - refresh (re-reads dir)
For files:
 - open file (download and open in editor)
 - remove file
 
File, which was downloaded and edited, will be uploaded, when "Save" command runs.

Notes:
- Config file is "[Cudatext]/settings/cuda_ftp.json"
- No permanent connection to FTP is kept. Each request (read dir, download, upload...) 
makes new connection, then closes connection.

Homepage:
https://github.com/pohmelie/cuda_ftp
