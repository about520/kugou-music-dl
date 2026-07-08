# 酷狗音乐下载器

通过 Web 界面搜索并下载酷狗音乐免费歌曲，手机电脑都能用。

## 快速启动

```bash
pip install requests
python kugou_web.py
```

启动后终端会显示两个地址：
- 电脑访问: `http://localhost:8899`
- 手机访问: `http://你电脑局域网IP:8899`

同一 WiFi 下的手机浏览器输入手机访问地址即可搜歌下载。

## 项目结构

- `kugou_spider.py` — 核心爬虫（搜索/获取播放链接/下载）
- `kugou_web.py` — Web 服务（提供手机端友好界面）
- `kugou_downloads/` — 下载目录

## 注意

- 仅支持免费歌曲下载
- VIP 付费歌曲会提示"付费"，无法下载
