# Anime_Crawler

`Anime_Crawler` 是一个基于 Python 的自动化视频下载工具，旨在从支持 m3u8 格式的视频流网站下载视频集。它使用 Selenium-wire 自动化浏览器操作，提取并下载 m3u8 视频流的片段，并最终合并成一个完整的视频文件。

## 特性

- **自动提取视频集链接**：从页面中提取所有可用的视频集链接。
- **下载 m3u8 格式的视频流**：下载 m3u8 视频流的所有片段（`.ts` 文件）。
- **多线程下载**：支持并行下载视频片段，提升下载效率。
- **下载进度保存与恢复**：避免重复下载，支持进度保存。
- **合并视频片段**：下载完成后，自动使用 FFmpeg 合并视频片段，生成完整的 `.mp4` 文件。
- **用户交互**：允许用户选择下载特定集数或全部集数，支持更换网址。

## 依赖

在运行此脚本之前，请确保已安装以下 Python 库：

- `selenium`：用于自动化浏览器操作。
- `requests`：用于下载 `.ts` 视频片段。
- `m3u8`：用于解析 m3u8 播放列表。
- `beautifulsoup4`：用于解析 HTML 内容并提取视频集信息。
- `tqdm`：用于显示下载进度条。
- `webdriver_manager`：用于自动安装和管理 ChromeDriver。
- `ffmpeg`：用于将 `.ts` 片段合并为 `.mp4` 视频文件。

你可以使用以下命令安装所有依赖：

```bash
pip install selenium-wire blinker==1.4 requests m3u8 webdriver-manager beautifulsoup4 tqdm
```

此外，你需要安装 [FFmpeg](https://ffmpeg.org/) 并将其添加到系统的 PATH 中。

## 使用方法

### 配置文件

`config.json` 文件用于配置下载器的设置，如下载线程数、保存视频片段的文件夹等。以下是默认配置文件内容：

```json
{
  "thread_count": 5,
  "ts_folder": "ts_files",
  "progress_file": "progress.txt"
}
```

- `thread_count`: 并行下载的线程数，默认值为 5。
- `ts_folder`: 存放 `.ts` 片段的文件夹，默认值为 `ts_files`。
- `progress_file`: 存储下载进度的文件，默认值为 `progress.txt`。

### 启动脚本

运行以下命令启动下载器：

```bash
python main.py
```

### 用户交互

- 输入 `Enter` 确认当前网址并显示所有可下载的视频集。
- 输入 `clear` 更换当前网址。
- 输入 `exit` 退出程序。
- 用户可以选择下载所有集数，或者输入特定集数（如 `1,2,3` 或 `1-3`）进行下载。

### 下载过程

- 程序会自动提取 m3u8 链接，下载所有视频片段（`.ts` 文件），并使用 FFmpeg 将片段合并为一个 `.mp4` 文件。
- 下载过程中会显示进度条，显示当前片段的下载状态。

### 示例

运行脚本时，输出类似如下内容：

```bash
$ python main.py
当前网址: https://yhdm6.top/
1. Enter 确认当前网址
2. 输入 'clear' 更换网址
3. 输入 'exit' 退出程序
请输入你的选择: 
```

## 注意事项

- 请确保你的网络稳定，因为视频片段较大且需要较长时间下载。
- FFmpeg 命令会将 `.ts` 文件合并，合并过程中可能会花费一些时间。
- 如果中途下载失败或脚本崩溃，程序会记录进度，下一次运行时会继续下载未完成的片段。

## 使用教程

[YouTube](https://youtu.be/3K6PtbxCHTs) [Bilibili](https://www.bilibili.com/video/BV1FRFNerEyU)