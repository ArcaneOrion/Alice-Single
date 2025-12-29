#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微博热搜榜获取工具

通过微博内部 API 获取实时热搜榜数据
"""

import requests
import json
import argparse

def get_weibo_hot(limit=20):
    """
    获取微博热搜榜
    
    Args:
        limit: 获取热搜条目的数量，默认 20 条
        
    Returns:
        list: 热搜列表，每个元素包含 word, num, category 等信息
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://weibo.com/'
    }
    
    url = "https://weibo.com/ajax/side/hotSearch"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if 'data' in data and 'realtime' in data['data']:
            hot_list = data['data']['realtime'][:limit]
            return hot_list
        else:
            print("❌ 数据结构异常，无法解析热搜列表")
            return []
            
    except requests.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}")
        return []
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return []

def format_hot_list(hot_list):
    """
    格式化热搜榜输出
    
    Args:
        hot_list: 热搜列表
        
    Returns:
        str: 格式化后的文本
    """
    if not hot_list:
        return "暂无热搜数据"
    
    lines = ["🔥 微博热搜榜", "─" * 50]
    
    for i, item in enumerate(hot_list, 1):
        word = item.get('word', '未知')
        hot = item.get('num', 0)
        # 格式化热度数值
        if isinstance(hot, int):
            hot_str = f"{hot:,}"
        else:
            hot_str = str(hot)
        
        line = f"{i:2d}. {word:<30} 🔥 {hot_str}"
        lines.append(line)
    
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description='获取微博热搜榜')
    parser.add_argument('-l', '--limit', type=int, default=20,
                       help='获取热搜条目的数量 (默认: 20)')
    parser.add_argument('--raw', action='store_true',
                       help='输出原始 JSON 数据')
    
    args = parser.parse_args()
    
    hot_list = get_weibo_hot(args.limit)
    
    if args.raw:
        # 输出原始 JSON
        print(json.dumps(hot_list, ensure_ascii=False, indent=2))
    else:
        # 输出格式化文本
        print(format_hot_list(hot_list))

if __name__ == "__main__":
    main()
