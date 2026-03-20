import asyncio
import httpx
from bs4 import BeautifulSoup

URL = "https://quotes.toscrape.com"

async def scrape():

    async with httpx.AsyncClient() as client:

        r = await client.get(URL)

        soup = BeautifulSoup(r.text, "html.parser")

        quotes = soup.select(".quote")

        for q in quotes[:5]:

            text = q.select_one(".text").text
            author = q.select_one(".author").text

            print(author, ":", text)

asyncio.run(scrape())