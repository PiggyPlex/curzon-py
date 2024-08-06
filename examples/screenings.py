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

  print('=' * 20)
  print('First Screening:')
  print('Screen:', screenings[0].screen)
  print('Starts:', screenings[0].starts_at.strftime('%I:%M %p'))
  print('Film Starts:', screenings[0].film_starts_at.strftime('%I:%M %p'))
  print('Available Seats: ', end='')
  # Find all available seats
  seats = await screenings[0].get_seats()
  available_seats = []
  for seat in seats:
    if seat.status == 'Available':
      available_seats.append(seat)
  def format_seat(seat):
    text = seat.name
    if seat.type == 'Wheelchair':
      text += ' (W)'
    if seat.type == 'Companion':
      text += ' (C)'
    return text
  print(', '.join(map(format_seat, available_seats)))

  # Find the ticket price of an adult for this screening
  ticket_types = await screenings[0].get_ticket_prices()
  adult_ticket = next((ticket_type for ticket_type in ticket_types if ticket_type.name == 'Adult'), None)
  print(f'Adult Ticket Price: £{adult_ticket.price:.2f}' if adult_ticket else 'Unknown')

asyncio.run(main())