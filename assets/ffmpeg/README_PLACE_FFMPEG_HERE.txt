Windows 打包前请把静态 win64 二进制放到本目录：

  ffmpeg.exe
  ffprobe.exe

推荐来源（任选其一，注意许可证）：
  - https://www.gyan.dev/ffmpeg/builds/  → ffmpeg-release-essentials.zip
  - https://github.com/BtbN/FFmpeg-Builds/releases → win64 gpl 共享构建

解压后把 bin/ffmpeg.exe 与 bin/ffprobe.exe 复制到本目录。
packaging/build_windows.ps1 会在打包前检查这两个文件是否存在。
本目录留空时，开发机仍可走系统 PATH 里的 ffmpeg（仅 Linux/mac 开发）。
