import os
import requests
import m3u8
from urllib.parse import urljoin
import subprocess
import logging
from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor
import json
import time
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# 检查日志文件是否存在，存在就清空，不存在则创建一个新的空文件
log_file = 'app.log'
if os.path.exists(log_file):
    open(log_file, 'w').close()  # 清空日志文件
else:
    open(log_file, 'w').close()  # 创建新的空日志文件

# 设置日志
logging.basicConfig(level=logging.INFO, filename=log_file, format='%(asctime)s - %(levelname)s - %(message)s')

class VideoDownloader:
    def __init__(self, base_url, config_file='config.json'):
        # 初始化 VideoDownloader 类
        self.base_url = base_url  # 基础网址
        self.config = self.load_config(config_file)  # 加载配置文件
        self.driver = self.init_driver()  # 初始化 Selenium WebDriver

    @staticmethod
    def load_config(config_file):
        # 加载配置文件
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)  # 返回配置内容
        return {
            "thread_count": 5,  # 默认线程数
            "ts_folder": "ts_files",  # TS 文件存储文件夹
            "progress_file": "progress.txt"  # 进度文件
        }

    @staticmethod
    def init_driver():
        # 初始化 Selenium WebDriver
        options = Options()
        options.add_argument("--start-maximized")  # 启动时最大化窗口
        options.add_argument("--disable-infobars")  # 禁用信息栏
        options.add_argument("--disable-extensions")  # 禁用扩展
        options.add_argument("--disable-gpu")  # 禁用 GPU 加速
        options.add_argument("--disable-dev-shm-usage")  # 解决资源限制问题
        options.add_argument("--no-sandbox")  # 禁用沙盒模式
        
        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            return driver  # 返回 WebDriver 实例
        except Exception as e:
            logging.error(f"初始化 ChromeDriver 时出错: {e}")  # 记录错误信息
            raise

    def extract_episodes(self):
        # 从当前页面提取剧集信息
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')  # 解析页面
        episodes = []  # 存储剧集信息的列表
        playlist = soup.find('ul', class_='content_playlist clearfix')  # 查找播放列表
        if playlist:
            for li in playlist.find_all('li'):
                a_tag = li.find('a')  # 查找每个剧集的链接
                if a_tag and 'href' in a_tag.attrs:
                    episode_title = a_tag.get_text(strip=True)  # 获取剧集标题
                    episode_link = urljoin(self.driver.current_url, a_tag['href'])  # 获取剧集链接
                    episodes.append((episode_title, episode_link))  # 添加到剧集列表
        return episodes  # 返回剧集列表

    def open_devtools_and_network(self):
        # 打开开发者工具并切换到网络选项卡
        actions = ActionChains(self.driver)
        
        # 打开开发者工具
        actions.send_keys('\ue03c')  
        actions.perform()
        time.sleep(2)  # 等待 DevTools 打开

        # 切换到 Network 选项卡
        actions.send_keys(Keys.CONTROL + '2')  
        actions.perform()
        time.sleep(4)  # 等待 4 秒以便网络请求被捕获

        # 关闭 DevTools
        actions.send_keys('\ue03c')  
        actions.perform()

    def extract_m3u8_url(self):
        # 提取 m3u8 链接
        try:
            # 调用打开 DevTools 和切换到 Network 的函数
            self.open_devtools_and_network()

            WebDriverWait(self.driver, 10).until(lambda d: len(d.requests) > 0)  # 等待请求被捕获
            
            m3u8_urls = []  # 存储 m3u8 链接的列表
            # 收集所有的 m3u8 链接

            for request in self.driver.requests:
                if "m3u8" in request.url:
                    m3u8_urls.append(request.url)  # 添加 m3u8 链接
            
            # 确保至少有两个 m3u8 链接，返回 index 1 的链接（即第二个）  
            if len(m3u8_urls) > 1:
                # 将 m3u8 链接写入进度文件的第一行
                with open(self.config['progress_file'], 'w') as f:
                    f.write(m3u8_urls[1] + '\n')  # 写入 m3u8 链接
                return m3u8_urls[1]  # 获取第二个 m3u8 链接
            
        except Exception as e:
            logging.error(f"提取 m3u8 链接失败: {e}")  # 记录错误信息
        return None  # 返回 None 表示未找到链接

    def download_episode(self, episode):
        # 下载指定剧集
        title, link = episode  # 解包剧集信息
        logging.info(f"正在处理: {title}")  # 记录正在处理的剧集
        self.driver.get(link)  # 打开剧集链接

        m3u8_url = self.extract_m3u8_url()  # 提取 m3u8 链接
        if m3u8_url:
            logging.info(f"发现 m3u8 链接: {m3u8_url}")  # 记录找到的 m3u8 链接
            output_file = f"{title}.mp4"  # 设置输出文件名
            self.download_video(m3u8_url, output_file)  # 下载视频
        else:
            logging.warning(f"未找到 m3u8 文件链接: {link}")  # 记录未找到链接的警告
        
        # 关闭并重新启动 WebDriver 以清除缓存
        self.close_driver()
        self.driver = self.init_driver()  # 重新初始化 WebDriver

    def download_video(self, m3u8_url, output_video_filename):
        # 下载视频
        playlist = m3u8.load(m3u8_url)  # 加载 m3u8 播放列表
        ts_folder = self.config['ts_folder']  # 获取 TS 文件夹路径
        progress_file = self.config['progress_file']  # 获取进度文件路径

        os.makedirs(ts_folder, exist_ok=True)  # 创建 TS 文件夹
        base_url = m3u8_url.rsplit('/', 1)[0] + '/'  # 获取基础 URL
        completed_files = self.load_progress(progress_file)  # 加载已完成的文件

        segments = [(idx, urljoin(base_url, segment.uri)) for idx, segment in enumerate(playlist.segments) if idx not in completed_files]  # 获取未下载的片段

        def download_segment(segment):
            # 下载单个 TS 片段
            idx, ts_url = segment  # 解包片段信息
            ts_filename = os.path.join(ts_folder, f"{idx}.ts")  # 设置 TS 文件名
            self.download_ts_file_with_retry(ts_url, ts_filename)  # 下载 TS 文件
            completed_files.add(idx)  # 添加到已完成列表
            self.save_progress(progress_file, completed_files)  # 保存进度

        with ThreadPoolExecutor(max_workers=self.config['thread_count']) as executor:
            list(tqdm(executor.map(download_segment, segments), total=len(segments), desc="下载片段"))  # 并行下载 TS 片段

        # 修改点：这里传入了 progress_file 参数
        self.merge_ts_files(ts_folder, output_video_filename, progress_file)  # 合并 TS 文件

    @staticmethod
    def download_ts_file_with_retry(ts_url, output_path, retries=3):
        # 下载 TS 文件并重试
        for attempt in range(retries):
            try:
                response = requests.get(ts_url, stream=True, timeout=10)  # 发送请求
                response.raise_for_status()  # 检查请求是否成功
                with open(output_path, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)  # 写入文件
                return  # 下载成功，返回
            except requests.exceptions.RequestException as e:
                logging.warning(f"下载 {ts_url} 失败 (尝试 {attempt + 1}/{retries}): {e}")  # 记录下载失败的警告
                if attempt == retries - 1:
                    raise  # 超过重试次数，抛出异常

    @staticmethod
    def merge_ts_files(ts_folder, output_video_filename, progress_file):
        # 合并 TS 文件为视频
        list_file = "ts_list.txt"  # 临时列表文件
        with open(list_file, "w") as f:
            for ts_file in sorted(os.listdir(ts_folder), key=lambda x: int(x.split('.')[0])):
                f.write(f"file '{os.path.join(ts_folder, ts_file)}'\n")  # 写入 TS 文件路径

        # 使用 FFmpeg 合成视频
        cmd = f'ffmpeg -f concat -safe 0 -i {list_file} -c copy "{output_video_filename}"'
        subprocess.run(cmd, shell=True)  # 执行合并命令

        # 删除临时 TS 文件夹及文件
        os.remove(list_file)  # 删除列表文件
        for ts_file in os.listdir(ts_folder):
            os.remove(os.path.join(ts_folder, ts_file))  # 删除 TS 文件
        os.rmdir(ts_folder)  # 删除 TS 文件夹
        logging.info(f"视频已合并为 {output_video_filename}")  # 记录合并成功的信息

        # 删除进度文件
        if os.path.exists(progress_file):
            os.remove(progress_file)  # 删除进度文件
            logging.info(f"删除进度文件: {progress_file}")  # 记录删除进度文件的信息

    @staticmethod
    def load_progress(progress_file):
        # 加载进度文件
        if os.path.exists(progress_file):
            with open(progress_file, 'r') as f:
                return set(map(int, f.read().splitlines()))  # 返回已完成的文件索引集合
        return set()  # 返回空集合

    @staticmethod
    def save_progress(progress_file, completed_files):
        # 保存进度到文件
        with open(progress_file, 'w') as f:
            for idx in sorted(completed_files):
                f.write(f"{idx}\n")  # 写入已完成的文件索引

    def handle_user_input(self):
        # 处理用户输入
        while True:
            print(f"\n当前网址: {self.driver.current_url}")  # 显示当前网址
            user_input = input("1. Enter 确认当前网址\n2. 输入 'clear' 更换网址\n3. 输入 'exit' 退出程序\n请输入你的选择: ").strip().lower()

            if user_input == "exit":
                print("程序已退出。")  # 退出提示
                break
            elif user_input == "":
                # 检查是否存在进度文件
                if os.path.exists(self.config['progress_file']):
                    restore_choice = input("检测到进度文件，是否恢复下载进度？(y/n): ").strip().lower()
                    if restore_choice == 'y':
                        # 从进度文件中读取链接和进度
                        with open(self.config['progress_file'], 'r') as f:
                            m3u8_url = f.readline().strip()  # 读取第一行 m3u8 链接
                            completed_files = self.load_progress(self.config['progress_file'])  # 加载已完成的文件
                        # 继续下载
                        self.download_video(m3u8_url, completed_files)
                        continue  # 继续循环
                    else:
                        # 删除所有相关文件
                        os.remove(self.config['progress_file'])
                        ts_folder = self.config['ts_folder']
                        if os.path.exists(ts_folder):
                            for ts_file in os.listdir(ts_folder):
                                os.remove(os.path.join(ts_folder, ts_file))  # 删除 TS 文件
                            os.rmdir(ts_folder)  # 删除 TS 文件夹
                        print("已删除进度文件和相关文件。")

                episodes = self.extract_episodes()  # 提取剧集
                if episodes:
                    for idx, (title, link) in enumerate(episodes, 1):
                        print(f"{idx}. {title} - {link}")  # 显示剧集列表

                    download_choice = input("输入 'all' 下载所有集数，或输入特定集数 (如 1,2,3 或 1-3): ").strip().lower()
                    if download_choice == "all":
                        for episode in episodes:
                            self.download_episode(episode)  # 下载所有剧集
                    else:
                        try:
                            # 如果输入是范围格式 (如 1-2)
                            if '-' in download_choice:
                                start, end = map(int, download_choice.split('-'))
                                for i in range(start, end + 1):
                                    self.download_episode(episodes[i - 1])  # 索引是从0开始的
                            else:
                                episode_numbers = [int(num) for num in download_choice.split(',')]
                                for number in episode_numbers:
                                    self.download_episode(episodes[number - 1])  # 下载指定剧集
                        except (ValueError, IndexError):
                            print("输入无效，请检查集数格式。")  # 输入格式错误提示

                    self.driver.get("https://yhdm6.top/")  # 下载完成后返回主页
                    print("已返回主页。")  # 提示用户已返回主页
                else:
                    print("未找到任何动漫集数。")  # 未找到剧集提示
            elif user_input == "clear":
                new_url = input("请输入新网址: ").strip()  # 输入新网址
                if new_url:
                    self.driver.get(new_url)  # 切换网址
                    print(f"已切换到新网址: {new_url}")  # 切换成功提示
            else:
                print("无效输入，请重试。")  # 无效输入提示

    def close_driver(self):
        # 关闭 WebDriver
        if self.driver:
            self.driver.quit()  # 退出 WebDriver

if __name__ == "__main__":
    downloader = VideoDownloader("https://yhdm6.top/")  # 创建 VideoDownloader 实例
    try:
        downloader.driver.get(downloader.base_url)  # 打开基础网址
        downloader.handle_user_input()  # 处理用户输入
    except Exception as e:
        logging.error(f"发生错误: {e}")  # 记录错误信息
    finally:
        downloader.close_driver()  # 关闭 WebDriver
        logging.info("程序已结束。")  # 记录程序结束信息