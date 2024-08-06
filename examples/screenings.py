# Get the list of screenings for a particular show from a particular cinema

# Import hack
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Code starts here
from curzon import Curzon

import asyncio
from datetime import datetime

SITE_ID = 'ALD1'
FILM_ID = 'HO00005424' # 'Deadpool & Wolverine'
DATE = datetime.now().strftime("%Y-%m-%d")

async def main():
  curzon = Curzon()
  success = await curzon.auth()
  if not success:
    print('Auth token couldn\'t be obtained')
    return
  print('Auth token obtained')
  sites = await curzon.get_sites()
  site = sites[SITE_ID]
  films = await curzon.get_films()
  film = films[FILM_ID]
  screenings = await film.get_screenings(site, DATE)
  print(f'All showings for {film.title} at {site.name} on {DATE}:')
  for screening in screenings:
    print('Screen', screening.screen, 'at', screening.starts_at.strftime('%I:%M %p'))

asyncio.run(main())