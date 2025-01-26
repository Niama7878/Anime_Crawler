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
        self.base_url = base_url
        self.config = self.load_config(config_file)
        self.driver = self.init_driver()

    @staticmethod
    def load_config(config_file):
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                return json.load(f)
        return {
            "thread_count": 5,
            "ts_folder": "ts_files",
            "progress_file": "progress.txt"
        }

    @staticmethod
    def init_driver():
        options = Options()
        options.add_argument("--start-maximized")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        try:
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            return driver
        except Exception as e:
            logging.error(f"初始化 ChromeDriver 时出错: {e}")
            raise

    def extract_episodes(self):
        soup = BeautifulSoup(self.driver.page_source, 'html.parser')
        episodes = []
        playlist = soup.find('ul', class_='content_playlist clearfix')
        if playlist:
            for li in playlist.find_all('li'):
                a_tag = li.find('a')
                if a_tag and 'href' in a_tag.attrs:
                    episode_title = a_tag.get_text(strip=True)
                    episode_link = urljoin(self.driver.current_url, a_tag['href'])
                    episodes.append((episode_title, episode_link))
        return episodes

    def extract_m3u8_url(self):
        try:
            WebDriverWait(self.driver, 10).until(lambda d: len(d.requests) > 0)
            
            m3u8_urls = []
            # 收集所有的 m3u8 链接
            for request in self.driver.requests:
                if "m3u8" in request.url:
                    m3u8_urls.append(request.url)
            
            # 确保至少有两个 m3u8 链接，返回 index 1 的链接（即第二个）  
            if len(m3u8_urls) > 1:
                return m3u8_urls[1]  # 获取第二个 m3u8 链接
            
        except Exception as e:
            logging.error(f"提取 m3u8 链接失败: {e}")
        return None

    def download_episode(self, episode):
        title, link = episode
        logging.info(f"正在处理: {title}")
        self.driver.get(link)

        m3u8_url = self.extract_m3u8_url()
        if m3u8_url:
            logging.info(f"发现 m3u8 链接: {m3u8_url}")
            output_file = f"{title}.mp4"
            self.download_video(m3u8_url, output_file)
        else:
            logging.warning(f"未找到 m3u8 文件链接: {link}")

    def download_video(self, m3u8_url, output_video_filename):
        playlist = m3u8.load(m3u8_url)
        ts_folder = self.config['ts_folder']
        progress_file = self.config['progress_file']

        os.makedirs(ts_folder, exist_ok=True)
        base_url = m3u8_url.rsplit('/', 1)[0] + '/'
        completed_files = self.load_progress(progress_file)

        segments = [(idx, urljoin(base_url, segment.uri)) for idx, segment in enumerate(playlist.segments) if idx not in completed_files]

        def download_segment(segment):
            idx, ts_url = segment
            ts_filename = os.path.join(ts_folder, f"{idx}.ts")
            self.download_ts_file_with_retry(ts_url, ts_filename)
            completed_files.add(idx)
            self.save_progress(progress_file, completed_files)

        with ThreadPoolExecutor(max_workers=self.config['thread_count']) as executor:
            list(tqdm(executor.map(download_segment, segments), total=len(segments), desc="下载片段"))

        # 修改点：这里传入了 progress_file 参数
        self.merge_ts_files(ts_folder, output_video_filename, progress_file)

    @staticmethod
    def download_ts_file_with_retry(ts_url, output_path, retries=3):
        for attempt in range(retries):
            try:
                response = requests.get(ts_url, stream=True, timeout=10)
                response.raise_for_status()
                with open(output_path, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
                return
            except requests.exceptions.RequestException as e:
                logging.warning(f"下载 {ts_url} 失败 (尝试 {attempt + 1}/{retries}): {e}")
                if attempt == retries - 1:
                    raise

    @staticmethod
    def merge_ts_files(ts_folder, output_video_filename, progress_file):
        list_file = "ts_list.txt"
        with open(list_file, "w") as f:
            for ts_file in sorted(os.listdir(ts_folder), key=lambda x: int(x.split('.')[0])):
                f.write(f"file '{os.path.join(ts_folder, ts_file)}'\n")

        # 使用 FFmpeg 合成视频
        cmd = f'ffmpeg -f concat -safe 0 -i {list_file} -c copy "{output_video_filename}"'
        subprocess.run(cmd, shell=True)

        # 删除临时 TS 文件夹及文件
        os.remove(list_file)
        for ts_file in os.listdir(ts_folder):
            os.remove(os.path.join(ts_folder, ts_file))
        os.rmdir(ts_folder)
        logging.info(f"视频已合并为 {output_video_filename}")

        # 删除进度文件
        if os.path.exists(progress_file):
            os.remove(progress_file)
            logging.info(f"删除进度文件: {progress_file}")

    @staticmethod
    def load_progress(progress_file):
        if os.path.exists(progress_file):
            with open(progress_file, 'r') as f:
                return set(map(int, f.read().splitlines()))
        return set()

    @staticmethod
    def save_progress(progress_file, completed_files):
        with open(progress_file, 'w') as f:
            for idx in sorted(completed_files):
                f.write(f"{idx}\n")

    def handle_user_input(self):
        while True:
            print(f"\n当前网址: {self.driver.current_url}")
            user_input = input("1. Enter 确认当前网址\n2. 输入 'clear' 更换网址\n3. 输入 'exit' 退出程序\n请输入你的选择: ").strip().lower()

            if user_input == "exit":
                print("程序已退出。")
                break
            elif user_input == "":
                episodes = self.extract_episodes()
                if episodes:
                    for idx, (title, link) in enumerate(episodes, 1):
                        print(f"{idx}. {title} - {link}")

                    download_choice = input("输入 'all' 下载所有集数，或输入特定集数 (如 1,2,3 或 1-3): ").strip().lower()
                    if download_choice == "all":
                        for episode in episodes:
                            self.download_episode(episode)
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
                                    self.download_episode(episodes[number - 1])
                        except (ValueError, IndexError):
                            print("输入无效，请检查集数格式。")
                else:
                    print("未找到任何动漫集数。")
            elif user_input == "clear":
                new_url = input("请输入新网址: ").strip()
                if new_url:
                    self.driver.get(new_url)
                    print(f"已切换到新网址: {new_url}")
            else:
                print("无效输入，请重试。")

    def close(self):
        if self.driver:
            self.driver.quit()

if __name__ == "__main__":
    downloader = VideoDownloader("https://yhdm6.top/")
    try:
        downloader.driver.get(downloader.base_url)
        downloader.handle_user_input()
    except Exception as e:
        logging.error(f"发生错误: {e}")
    finally:
        downloader.close()
        logging.info("程序已结束。")