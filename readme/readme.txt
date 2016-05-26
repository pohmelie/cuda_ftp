Plugin for CudaText.
Allows to open/edit/save/remove/create remote FTP files and directories.

Notes:
- Config file is "[Cudatext]/settings/cuda_ftp.json"
- No permanent connection to FTP is kept. Each request (list dir, download, upload) makes new connection, then closes connection.
