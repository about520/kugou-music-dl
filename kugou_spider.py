#!/usr/bin/env python3
"""
酷狗音乐爬虫 —— 支持搜索、获取播放链接、下载MP3
会员歌曲需填入登录后的 Cookie 才能获取完整音质链接。
用法：
    python kugou_spider.py search 周杰伦          # 搜索歌曲
    python kugou_spider.py download <hash> <album_id>  # 下载指定歌曲
    python kugou_spider.py vip 热门歌单            # 带Cookie爬会员歌曲
"""

import json
import os
import re
import sys
import time
import random
import argparse

import requests

# ============ 配置区 ============
# 从浏览器登录酷狗后，F12 → Application → Cookies，复制以下字段的值
COOKIES = {
    "kg_mid": "b84b2f1512468f171a6033b32a42ed8d",
    "kg_dfid": "1Jg03x0UJAzy2wVjbr3PcDq0",
    "kg_dfid_collect": "d41d8cd98f00b204e9800998ecf8427e",
    "Hm_lvt_aedee6983d4cfc62f509129360d6bb3d": "1783490738",
    "Hm_lpvt_aedee6983d4cfc62f509129360d6bb3d": "1783490849",
    "HMACCOUNT": "38A3D6E7FE6B0E5B",
    "kg_mid_temp": "b84b2f1512468f171a6033b32a42ed8d",
    "KuGoo": "KugooID=1663795057&KugooPwd=6D88338E047708E3407FC4844668917C&NickName=%u5feb%u4e50&Pic=http://imge.kugou.com/kugouicon/165/20250722/20250722120430470988.jpg&RegState=1&RegFrom=&t=ad0d2a175958b3a5cb743468e71ae70dfa024c14c5e0a5f5802fbcf5e5143d55&a_id=1014&ct=1783490799&UserName=%u006b%u0067%u006f%u0070%u0065%u006e%u0031%u0036%u0036%u0037%u0039%u0035%u0030%u0035%u0037&t1=",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "Referer": "https://www.kugou.com/",
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "kugou_downloads")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update(HEADERS)
if COOKIES:
    SESSION.cookies.update(COOKIES)


# ============ 核心API ============

def search_songs(keyword: str, page: int = 1, pagesize: int = 30) -> list[dict]:
    """搜索歌曲，返回歌曲列表"""
    url = "https://songsearch.kugou.com/song_search_v2"
    params = {
        "keyword": keyword,
        "page": page,
        "pagesize": pagesize,
        "userid": -1,
        "clientver": "",
        "platform": "WebFilter",
        "tag": "em",
        "filter": 2,
        "iscorrection": 1,
        "privilege_filter": 0,
    }
    resp = SESSION.get(url, params=params, timeout=15)
    data = resp.json()
    songs = []
    for item in data.get("data", {}).get("lists", []):
        songs.append({
            "name": item.get("SongName", "").replace("<em>", "").replace("</em>", ""),
            "singer": item.get("SingerName", ""),
            "album": item.get("AlbumName", ""),
            "duration": item.get("Duration", 0),
            "hash": item.get("FileHash", ""),
            "album_id": item.get("AlbumID", ""),
            "sq_hash": item.get("SQFileHash", ""),
            "hq_hash": item.get("HQFileHash", ""),
            "mv_hash": item.get("MvHash", ""),
            "is_vip": item.get("privilege", 0) > 0 or str(item.get("PayType", "")) == "VIP",
        })
    return songs


def get_play_info(file_hash: str, album_id: str = "") -> dict:
    """获取歌曲播放链接和详细信息（使用移动端API）"""
    url = "https://m.kugou.com/app/i/getSongInfo.php"
    params = {
        "cmd": "playInfo",
        "hash": file_hash,
    }
    headers_m = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
                      "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
        "Referer": "https://m.kugou.com/",
    }

    resp = SESSION.get(url, params=params, headers=headers_m, timeout=15)
    data = resp.json()

    if data.get("status") != 0 and data.get("errcode") != 0:
        return {"error": data.get("errcode", -1), "msg": "获取失败"}

    # Extract song info and audio URL
    song_name = data.get("songName", "")
    singer = data.get("singerName", "") or data.get("author_name", "")
    play_url = data.get("url", "") or ""
    backup_urls = data.get("backup_url", {}) or {}
    extra = data.get("extra", {})

    return {
        "name": song_name,
        "singer": singer,
        "album": "",
        "img": data.get("imgUrl", ""),
        "play_url": play_url,
        "play_backup_url": backup_urls[0] if isinstance(backup_urls, list) and backup_urls else "",
        "lyrics": data.get("intro", ""),
        "filesize": data.get("fileSize", 0),
        "bitrate": extra.get("128bitrate", data.get("bitRate", 0)),
        "timelength": data.get("timeLength", extra.get("128timelength", 0)),
        "is_vip": False,  # mobile API doesn't expose this directly
        "extName": data.get("extName", "mp3"),
        "sq_hash": extra.get("sqhash", ""),
        "hq_hash": extra.get("highhash", ""),
        "hash_320": extra.get("320hash", ""),
    }


def download_song(play_url: str, filename: str) -> str:
    """下载MP3文件，返回保存路径"""
    resp = SESSION.get(play_url, stream=True, timeout=60)
    resp.raise_for_status()

    safe_name = re.sub(r'[\\/*?:"<>|]', "_", filename)
    filepath = os.path.join(OUTPUT_DIR, f"{safe_name}.mp3")

    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(filepath, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded * 100 // total
                print(f"\r  下载进度: {pct}% ({downloaded}/{total})", end="", flush=True)
    print()
    return filepath


def get_vip_playlist(playlist_id: str or int) -> list[dict]:
    """获取歌单歌曲列表（含会员歌）"""
    url = "https://m.kugou.com/plist/index"
    params = {
        "json": "true",
        "id": playlist_id,
    }
    resp = SESSION.get(url, params=params, timeout=15)
    data = resp.json()
    songs = []
    for item in data.get("list", {}).get("list", {}).get("info", []):
        songs.append({
            "name": item.get("filename", "").split(" - ")[-1] if " - " in item.get("filename", "") else item.get("filename", ""),
            "singer": item.get("filename", "").split(" - ")[0] if " - " in item.get("filename", "") else "",
            "hash": item.get("hash", ""),
            "album_id": item.get("album_id", ""),
            "is_vip": item.get("is_vip", False),
        })
    return songs


# ============ 交互命令 ============

def cmd_search(args):
    keyword = args.keyword
    print(f"\n搜索: {keyword}\n")
    print(f"{'序号':<5}{'歌名':<30}{'歌手':<20}{'时长':<10}{'VIP':<6}")
    print("-" * 75)

    songs = search_songs(keyword, page=args.page)
    for i, s in enumerate(songs, 1):
        mins = s["duration"] // 60
        secs = s["duration"] % 60
        vip = "🔒VIP" if s["is_vip"] else ""
        print(f"{i:<5}{s['name'][:28]:<30}{s['singer'][:18]:<20}{mins}:{secs:02d}   {vip}")

    # 保存到文件
    json_path = os.path.join(OUTPUT_DIR, f"search_{keyword}_{int(time.time())}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(songs, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {json_path}")
    print(f"共 {len(songs)} 首，下载请用：python kugou_spider.py download <hash> <album_id> [文件名]")


def cmd_download(args):
    file_hash = args.hash
    album_id = args.album_id or ""

    print(f"\n获取歌曲信息... hash={file_hash}")
    info = get_play_info(file_hash, album_id)

    if "error" in info:
        print(f"获取失败: {info['msg']}")
        return

    print(f"歌名: {info['name']}")
    print(f"歌手: {info['singer']}")
    print(f"音质: {info['bitrate']}kbps | 大小: {info['filesize']/1024/1024:.1f}MB")

    if info.get("is_vip"):
        print("⚠️  这是VIP歌曲，未登录可能无法下载完整音质")

    play_url = info.get("play_url") or info.get("play_backup_url")
    if not play_url:
        print("未获取到播放链接，可能需要登录Cookie")
        return

    filename = args.name or f"{info['singer']} - {info['name']}"
    print(f"开始下载: {filename}")
    filepath = download_song(play_url, filename)
    print(f"下载完成: {filepath}")


def cmd_batch(args):
    """批量下载搜索结果"""
    keyword = args.keyword
    count = args.count
    print(f"\n批量下载: {keyword} (最多 {count} 首)\n")

    songs = search_songs(keyword, page=1, pagesize=count)
    success = 0
    for i, s in enumerate(songs[:count], 1):
        print(f"[{i}/{count}] {s['singer']} - {s['name']}")
        info = get_play_info(s["hash"], s["album_id"])
        play_url = info.get("play_url") or info.get("play_backup_url")
        if play_url:
            try:
                filename = f"{info['singer']} - {info['name']}"
                download_song(play_url, filename)
                success += 1
            except Exception as e:
                print(f"  下载失败: {e}")
        else:
            print("  无播放链接（可能是VIP歌曲，需Cookie）")
        time.sleep(random.uniform(1.5, 3))
    print(f"\n批量下载完成: {success}/{count} 首成功")


def cmd_vip(args):
    """VIP会员歌曲爬取（需要Cookie）"""
    if not COOKIES:
        print("❌ 请先在脚本顶部的 COOKIES 字典里填入酷狗登录后的 Cookie")
        print("   获取方式：浏览器登录 kugou.com → F12 → Application → Cookies → 复制 kg_mid, dfid 等")
        return

    keyword = args.keyword
    print(f"\n会员歌曲搜索: {keyword}")
    songs = search_songs(keyword, page=1, pagesize=50)
    vip_songs = [s for s in songs if s["is_vip"]]
    print(f"共找到 {len(vip_songs)} 首VIP歌曲")

    for i, s in enumerate(vip_songs, 1):
        print(f"\n[{i}] {s['singer']} - {s['name']}")
        info = get_play_info(s["hash"], s["album_id"])
        play_url = info.get("play_url") or info.get("play_backup_url")
        if play_url:
            try:
                filename = f"{info['singer']} - {info['name']}"
                download_song(play_url, filename)
            except Exception as e:
                print(f"  下载失败: {e}")
        else:
            print("  无播放链接")
        time.sleep(random.uniform(2, 4))


def cmd_playlist(args):
    """爬取歌单"""
    pid = args.playlist_id
    print(f"\n获取歌单: {pid}")
    songs = get_vip_playlist(pid)
    print(f"共 {len(songs)} 首:\n")
    for i, s in enumerate(songs, 1):
        vip = "VIP" if s.get("is_vip") else ""
        print(f"  {i}. {s['singer']} - {s['name']}  {vip}")


# ============ 主入口 ============

def main():
    parser = argparse.ArgumentParser(description="酷狗音乐爬虫")
    sub = parser.add_subparsers(dest="command")

    # 搜索
    p_search = sub.add_parser("search", help="搜索歌曲")
    p_search.add_argument("keyword", help="搜索关键词")
    p_search.add_argument("-p", "--page", type=int, default=1)
    p_search.set_defaults(func=cmd_search)

    # 下载
    p_dl = sub.add_parser("download", help="下载单曲")
    p_dl.add_argument("hash", help="歌曲FileHash")
    p_dl.add_argument("album_id", nargs="?", default="", help="专辑AlbumID")
    p_dl.add_argument("-n", "--name", default="", help="自定义文件名（不含扩展名）")
    p_dl.set_defaults(func=cmd_download)

    # 批量下载
    p_batch = sub.add_parser("batch", help="批量下载搜索结果")
    p_batch.add_argument("keyword", help="搜索关键词")
    p_batch.add_argument("-c", "--count", type=int, default=10, help="下载数量（默认10）")
    p_batch.set_defaults(func=cmd_batch)

    # VIP
    p_vip = sub.add_parser("vip", help="会员歌曲搜索下载（需Cookie）")
    p_vip.add_argument("keyword", help="搜索关键词")
    p_vip.set_defaults(func=cmd_vip)

    # 歌单
    p_list = sub.add_parser("playlist", help="爬取歌单")
    p_list.add_argument("playlist_id", help="歌单ID")
    p_list.set_defaults(func=cmd_playlist)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
