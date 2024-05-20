import random
import time
import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading
from playwright.sync_api import sync_playwright
import asyncio
from playwright.async_api import async_playwright
import pandas as pd
import numpy as np
import csv
import os


if not os.path.exists('douban_books.csv'):
    with open('douban_books.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['书名', '评分', '作者/编译/出版社/出版时间/定价', '纸质版价格', '简介'])

# 检查文件是否为空，如果为空则添加列名
if os.path.exists('douban_books.csv') and os.stat('douban_books.csv').st_size == 0:
    with open('douban_books.csv', 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['书名', '评分', '作者/编译/出版社/出版时间/定价', '纸质版价格', '简介'])


# 添加请求头设置
async def set_request_headers(route, request):
    await route.continue_(headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    })


async def handle_route(route):
    await set_request_headers(route)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        async def route_handler(route):
            await handle_route(route)

        page.on('route', route_handler)
        # 在这里执行您的其他操作

asyncio.run(main())


def get_page_count(tag):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        url = f"https://book.douban.com/tag/{tag}"
        page.goto(url)

        page_count = 1
        while True:
            next_button = page.query_selector('span.next a')
            if not next_button:
                break
            next_button.click()
            page_count += 1

            # 添加随机延时
            time.sleep(random.uniform(1, 3))

        browser.close()

        return page_count


# 添加异常处理
def handle_exceptions(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"An exception occurred: {str(e)}")
    return wrapper

@handle_exceptions


def crawl_and_analyze(tag):
    output_text.insert(tk.END, "开始爬取...\n")
    output_text.update_idletasks()

    page_count = get_page_count(tag)
    output_text.insert(tk.END, f'共发现{page_count}页数据\n')
    output_text.update_idletasks()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        with open('douban_books.csv', 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['书名', '评分', '作者/编译/出版社/出版时间/定价', '纸质版价格', '简介'])

            for page_num in range(1, page_count + 1):
                url = f'https://book.douban.com/tag/{tag}?start={(page_num - 1) * 20}'
                page.goto(url)
                books = page.query_selector_all('.subject-list .info h2 a')
                ratings = page.query_selector_all('.subject-list .rating_nums')
                authors = page.query_selector_all('.subject-list .pub')
                prices = page.query_selector_all('.subject-list .cart-actions .buy-info a')
                brief_intro = page.query_selector_all('.subject-list .info p')

                for book, rating, author, price, intro in zip(books, ratings, authors, prices, brief_intro):
                    writer.writerow(
                        [book.inner_text(),
                         rating.inner_text(),
                         author.inner_text(),
                         price.inner_text(),
                         intro.inner_text()]
                    )

                next_button = page.query_selector('span.next a')
                if not next_button:
                    break
                next_button.click()

        browser.close()

    df = pd.read_csv('douban_books.csv')
    df['书名'] = df['书名'].str.strip()

    price_ranges = [0, 20, 40, 60, 80, 100, np.inf]
    price_labels = ['0-20', '20-40', '40-60', '60-80', '80-100', '100+']
    df['纸质版价格'] = df['纸质版价格'].str.extract(r'(\d+\.\d+|\d+)').astype(float)
    df['价格段'] = pd.cut(df['纸质版价格'], bins=price_ranges, labels=price_labels, right=False)

    price_grouped = df.groupby('价格段', observed=False)['书名'].apply(lambda x: ','.join(x)).reset_index()
    price_grouped.to_csv(f'{tag}_books_price_merge.csv', index=False)

    rating_ranges = [0, 4, 5, 6, 7, 8, 9, np.inf]
    rating_labels = ['0-4', '4-5', '5-6', '6-7', '7-8', '8-9', '9+']
    df['评分'] = df['评分'].astype(float)
    df['评分段'] = pd.cut(df['评分'], bins=rating_ranges, labels=rating_labels, right=False)

    rating_grouped = df.groupby('评分段', observed=False)['书名'].apply(lambda x: ','.join(x)).reset_index()
    rating_grouped.to_csv(f'{tag}_books_rating_merge.csv', index=False)

    # 处理价格和评分数据，将每本书信息放在单独列中
    price_df = pd.read_csv(f'{tag}_books_price_merge.csv')
    rating_df = pd.read_csv(f'{tag}_books_rating_merge.csv')

    price_df['书名'] = price_df['书名'].str.split(',')
    price_df = price_df.explode('书名')

    rating_df['书名'] = rating_df['书名'].str.split(',')
    rating_df = rating_df.explode('书名')

    price_df.to_csv(f'{tag}_books_price_beautiful.csv', index=False)
    rating_df.to_csv(f'{tag}_books_rating_beautiful.csv', index=False)

    output_text.insert(tk.END, "爬取完成\n")
    output_text.update_idletasks()
    messagebox.showinfo("提示", "爬取完成")


def start_crawling(df):
    tag = tag_entry.get()
    output_text.delete('1.0', tk.END)
    output_text.insert(tk.END, f"开始爬取标签为'{tag}'的图书信息...\n")

    thread = threading.Thread(target=crawl_and_analyze, args=(tag,))
    thread.start()


def on_closing():
    try:
        root.destroy()
    except KeyboardInterrupt:
        pass


root = tk.Tk()
root.title("豆瓣图书爬虫和统计工具")

# GUI界面美化
root.geometry("800x600")

label = tk.Label(root, text="请输入要爬取的豆瓣图书标签：")
label.pack()

tag_entry = tk.Entry(root, width=50)
tag_entry.pack()

output_text = scrolledtext.ScrolledText(root, width=60, height=10)
output_text.pack()

df = pd.read_csv('douban_books.csv')

crawl_button = tk.Button(root, text="开始爬取和统计", command=lambda: start_crawling(df))
crawl_button.pack(side=tk.TOP)


root.mainloop()
