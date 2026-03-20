# import asyncio
# import aiohttp
# from bs4 import BeautifulSoup

# BASE_URL = "https://quotes.toscrape.com/page/{}/"

# async def fetch_html(session: aiohttp.ClientSession, url: str) -> str:
#     async with session.get(url) as response:
#         response.raise_for_status()
#         return await response.text()

# def parse_quotes(html: str) -> list[dict]:
#     soup = BeautifulSoup(html, "html.parser")
#     quotes = []

#     for quote_block in soup.select(".quote"):
#         text = quote_block.select_one(".text").get_text(strip=True)
#         author = quote_block.select_one(".author").get_text(strip=True)
#         tags = [tag.get_text(strip=True) for tag in quote_block.select(".tags .tag")]

#         quotes.append({
#             "text": text,
#             "author": author,
#             "tags": tags,
#         })

#     return quotes

# async def scrape_page(session: aiohttp.ClientSession, page_num: int) -> list[dict]:
#     url = BASE_URL.format(page_num)
#     html = await fetch_html(session, url)
#     return parse_quotes(html)

# async def main():
#     async with aiohttp.ClientSession(headers={"User-Agent": "CupidBot/1.0"}) as session:
#         # tasks = [scrape_page(session, page) for page in range(1, 4)]
#         tasks = [scrape_page(session, 2)]
#         pages = await asyncio.gather(*tasks)

#         all_quotes = [quote for page in pages for quote in page]

#         for q in all_quotes[:5]:
#             print(q["author"], "=>", q["text"])
#             print("tags:", ", ".join(q["tags"]))
#             print("-" * 40)

# asyncio.run(main())

# =====================================================================
# TODO: Fetch 3 posts from JSONPlaceholder concurrently.
# TODO: Scrape 2 pages from Quotes to Scrape concurrently.
# TODO: Add a semaphore so only 2 requests run at once.