from __future__ import annotations
from typing import Dict, Tuple, Optional, Any, cast, List
from types import SimpleNamespace
from fake_useragent import UserAgent
import requests
import re
import asyncio
from json import dump
from dateutil import parser

# Example raw data:
# {'id': '0000000146', 'name': {'givenName': 'Martin', 'familyName': 'Sheen', 'middleName': None}}
class CastAndCrew:
  def __init__(self, raw_data: dict) -> None:
    self.id = cast(Optional[str], raw_data['id'])
    if 'name' not in raw_data or not raw_data['name']:
      return
    self.givenName = cast(str, raw_data['name']['givenName'] or '')
    self.middleName = cast(str, raw_data['name']['middleName'] or '')
    self.familyName = cast(str, raw_data['name']['familyName'] or '')
    self.name = ' '.join(filter(lambda x: x, (raw_data['name']['givenName'], raw_data['name']['middleName'], raw_data['name']['familyName'])))
    self.roles: List[str] = []

  def set_roles(self, roles: List[str]):
    self.roles = roles

# Example raw data:
# {id: "HO00000006", classification: {text: "15", translations: []}, classificationDescription: {text: "15", translations: []}}
class CensorRating:
  def __init__(self, raw_data: dict) -> None:
    self.id = cast(Optional[str], raw_data['id'])
    if raw_data.get('classificationDescription'):
      # TODO: properly type
      if cast(Any, raw_data.get('classificationDescription')).get('text'):
        self.classification = cast(Optional[str], raw_data['classificationDescription']['text'])

  def set_note(self, note: str) -> None:
    self.note = note

# Example raw data:
# {id: "0000000002", name: {text: "Drama", translations: []}, description: {text: "Drama", translations: []}}
class Genre:
  def __init__(self, raw_data: dict) -> None:
    self.id = cast(Optional[str], raw_data['id'])
    if raw_data.get('name'):
      self.name = cast(Optional[str], raw_data['name']['text'])
    if raw_data.get('description'):
      self.description = cast(Optional[str], raw_data['description']['text'])

# Example raw data:
# {
#     "id": "HO00005424",
#     "title": {
#         "text": "Deadpool & Wolverine",
#         "translations": []
#     },
#     "synopsis": {
#         "text": "Deadpool's peaceful existence comes crashing down when the Time Variance Authority recruits him to help safeguard the multiverse.",
#         "translations": []
#     },
#     "shortSynopsis": {
#         "text": "Deadpool's peaceful existence comes crashing down when the Time Variance Authority recruits him to help safeguard the multiverse.",
#         "translations": []
#     },
#     "censorRatingId": "HO00000006",
#     "censorRatingNote": {
#         "text": "strong bloody violence, injury detail, sex references, very strong language",
#         "translations": []
#     },
#     "releaseDate": "2024-07-25",
#     "runtimeInMinutes": 128,
#     "trailerUrl": null,
#     "displayPriority": 1,
#     "castAndCrew": [
#         {
#             "castAndCrewMemberId": "0000000316",
#             "roles": [
#                 "Actor"
#             ]
#         },
#         ...
#     ],
#     "genreIds": [
#         "0000000003",
#         ...
#     ],
#     "externalIds": {
#         "moviexchangeReleaseId": "00ee5871-dbed-4813-8461-8ebd59921981",
#         "corporateId": null
#     },
#     "hopk": "HO00005424",
#     "hoCode": "A000006717",
#     "eventId": null,
#     "distributorName": "Walt Disney Studios Motion Pictures - UK"
# }
class Film:
  # Data passed through from Curzon via dependency injection
  def __init__(self, curzon: Curzon, raw_data: dict, all_cast_and_crew: Dict[str, CastAndCrew], ratings: Dict[str, CensorRating], all_genres: Dict[str, Genre]) -> None:
    self._curzon = curzon

    self.id = cast(Optional[str], raw_data.get('id'))
    self.title = cast(Optional[str], raw_data.get('title', {}).get('text') if raw_data.get('title') else None)
    self.synopsis = cast(Optional[str], raw_data.get('synopsis', {}).get('text') if raw_data.get('synopsis') else None)
    self.shortSynopsis = cast(Optional[str], raw_data.get('shortSynopsis', {}).get('text') if raw_data.get('shortSynopsis') else None)

    self.released = cast(Optional[str], raw_data.get('releaseDate'))
    self.runtime = cast(Optional[int], raw_data.get('runtimeInMinutes'))

    self.trailerUri = cast(Optional[int], raw_data.get('trailerUrl'))
    self.displayPriority = cast(Optional[int], raw_data.get('displayPriority'))

    rating_id = raw_data.get('censorRatingId')
    self.rating: Optional[CensorRating] = ratings.get(rating_id) if rating_id else None

    rating_note = (raw_data.get('censorRatingNote', {}) or {}).get('text')
    if rating_note and 'text' in rating_note and self.rating:
      self.rating.set_note(rating_note['text'])

    self.cast_and_crew = cast(List[CastAndCrew], [])
    raw_cast_and_crew = raw_data.get('castAndCrew')
    if raw_cast_and_crew:
      for raw_entity in raw_cast_and_crew:
        id = raw_entity.get('castAndCrewMemberId')
        if not id:
          continue
        entity = all_cast_and_crew.get(id)
        if not entity:
          continue
        if raw_entity.get('roles'):
          entity.set_roles(raw_entity.get('roles'))
        self.cast_and_crew.append(entity)

    self.genres = cast(List[Genre], [])
    genre_ids = cast(Optional[List[str]], raw_data.get('genreIds'))
    if genre_ids:
      for id in genre_ids:
        genre = all_genres.get(id)
        if not genre:
          continue
        self.genres.append(genre)

    external_ids = raw_data.get('externalIds')
    if external_ids:
      self.moviexchange_id = cast(Optional[str], external_ids.get('moviexchangeReleaseId'))
      self.corporate_id = cast(Optional[str], external_ids.get('corporateId'))

    self.hopk = cast(Optional[str], raw_data.get('hopk'))
    self.hoCode = cast(Optional[str], raw_data.get('hoCode'))

    self.distributor = cast(Optional[str], raw_data.get('distributorName'))
    # TODO: implement event

  async def get_screenings(self, site: Site, date: str) -> List[Screening]:
    if not site.id:
      return []
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
      print('Invalid date.')
      return []
    json, error = await self._curzon.api(f'showtimes/by-business-date/{date}?siteIds={site.id}&filmIds={self.id}')
    if error or not json:
      return []
    raw_screenings = json.get('showtimes')
    if not raw_screenings:
      return []
    screenings = cast(List[Screening], [])
    for entity in raw_screenings:
      screenings.append(Screening(entity))
    return screenings

# Example raw data:
# {
#     "id": "ALD1-50641",
#     "schedule": {
#         "businessDate": "2024-08-06",
#         "startsAt": "2024-08-06T11:00:00+01:00",
#         "endsAt": "2024-08-06T13:33:00+01:00",
#         "filmStartsAt": "2024-08-06T11:25:00+01:00",
#         "filmEndsAt": "2024-08-06T13:33:00+01:00"
#     },
#     "isSoldOut": false,
#     "seatLayoutId": 3,
#     "filmId": "HO00005424",
#     "siteId": "ALD1",
#     "screenId": "ALD1-3",
#     "attributeIds": [],
#     "isAllocatedSeating": true,
#     "requires3dGlasses": false,
#     "eventId": null,
#     "restrictions": [],
#     "filmAdvanceBookingRuleId": null
# }
class Screening:
  def __init__(self, raw_data: dict) -> None:
    self.id = cast(Optional[str], raw_data.get('id'))

    schedule = cast(dict, raw_data.get('schedule'))
    if schedule:
      self.date = schedule.get('businessDate')
      starts_at = schedule.get('startsAt')
      if starts_at:
        self.starts_at = parser.parse(starts_at)
      ends_at = schedule.get('endsAt')
      if ends_at:
        self.ends_at = parser.parse(ends_at)
      film_starts_at = schedule.get('filmStartsAt')
      if film_starts_at:
        self.film_starts_at = parser.parse(film_starts_at)
      film_ends_at = schedule.get('filmEndsAt')
      if film_ends_at:
        self.film_ends_at = parser.parse(film_ends_at)

    self.is_sold_out = cast(bool, raw_data.get('is_sold_out', False) or False)
    self.seat_layout_id = cast(Optional[int], raw_data.get('seatLayoutId'))

    self.film_id = cast(Optional[str], raw_data.get('filmId'))
    self.site_id = cast(Optional[str], raw_data.get('siteid'))
    self.screenId = cast(Optional[str], raw_data.get('screenId'))
    if self.screenId:
      match = re.search(r'.*-(\d+)$', self.screenId)
      if match:
        self.screen: str = match.group(1)

    self.is_allocated_seating = cast(bool, raw_data.get('isAllocatedSeating', False) or False)
    self.requires_3d_glasses = cast(bool, raw_data.get('requires3dGlasses', False) or False)

    self.restrictions = cast(list, raw_data.get('restrictions', []) or [])
    # Unsure what this is used for. Type should be upadted if I find out.
    self.advance_booking_rule_id = cast(Optional[Any], raw_data.get('filmAdvanceBookingRuleId'))
    # TODO: implement attributes and event

# Example raw data:
# {
#     "id": "ALD1",
#     "name": {
#         "text": "Aldgate",
#         "translations": []
#     },
#     "location": {
#         "latitude": 51.5139,
#         "longitude": -0.069
#     },
#     "contactDetails": {
#         "phoneNumbers": [],
#         "email": "",
#         "address": {
#             "line1": "2 Canter Way,",
#             "line2": "London,",
#             "city": " E1 8PS"
#         }
#     },
#     "ianaTimeZoneName": "Europe/London"
# }

class SiteLocation:
  def __init__(self, raw_data: dict) -> None:
    lat = raw_data.get('latitude')
    if lat:
      self.latitude = lat
    lon = raw_data.get('longitude')
    if lon:
      self.longitude = lon

class SiteAddress:
  def __init__(self, raw_data: dict) -> None:
    line1 = raw_data.get('line1')
    if line1:
      self.line1 = line1
    line2 = raw_data.get('line2')
    if line2:
      self.line2 = line2
    city = raw_data.get('city')
    if city:
      self.city = city

class Site:
  def __init__(self, raw_data: dict) -> None:
    self.id = cast(Optional[str], raw_data.get('id'))
    if raw_data.get('name'):
      self.name = cast(Optional[str], raw_data['name']['text'])

    location = raw_data.get('location')
    if location:
      self.location = SiteLocation(location)

    contact_details = raw_data.get('contactDetails')
    if contact_details:
      address = contact_details.get('address')
      if address:
        self.address = SiteAddress(address)

class Curzon:
  API_BASE_URI: str = 'https://vwc.curzon.com/WSVistaWebClient/ocapi/v1'

  def __init__(self) -> None:
    self.ua = UserAgent()
    self.headers: Dict[str, str] = {'User-Agent': str(self.ua.chrome)}

  async def auth(self) -> bool:
    response = requests.get('https://www.curzon.com', headers=self.headers)
    match = re.search(r'"authToken":"(.+?)"', response.text)
    if not match:
      return False
    token = match.group(1)
    if not token:
      return False
    self.token = cast(str, token)
    self.headers = {
      **self.headers,
      'Authorization': f'Bearer {self.token}'
    }
    return True

  async def api(self, route: str, headers: Optional[Dict[str, str]] = None, **kwargs) -> Tuple[Optional[Dict[Any, Any]], Optional[Exception]]:
    if not self.token:
      return (None, Exception('Not authenticated. Authenticate first using #auth().'))
    if not route.startswith('/'):
      route = f'/{route}'
    if headers is None:
      headers = {}
    headers.update(self.headers)
    try:
      response = requests.get(f'{self.API_BASE_URI}{route}', headers=headers, **kwargs)
      json = response.json()
      return (json, None)
    except Exception as e:
      print(e)
      return (None, e)

  async def get_films(self) -> Dict[str, Film]:
    json, error = await self.api('films')
    if error or not json:
      return {}
    cast_and_crew = cast(Dict[str, CastAndCrew], {})
    for entity in json['relatedData']['castAndCrew']:
      cast_and_crew[entity['id']] = CastAndCrew(entity)
    ratings = cast(Dict[str, CensorRating], {})
    for entity in json['relatedData']['censorRatings']:
      ratings[entity['id']] = CensorRating(entity)
    genres = cast(Dict[str, Genre], {})
    for entity in json['relatedData']['genres']:
      genres[entity['id']] = Genre(entity)
    films = cast(Dict[str, Film], {})
    for raw_film in json['films']:
      films[raw_film['id']] = Film(self, raw_film, cast_and_crew, ratings, genres)
    return films

  async def get_sites(self) -> Dict[str, Site]:
    json, error = await self.api('sites')
    if error or not json:
      return {}
    sites = cast(Dict[str, Site], {})
    raw_sites = cast(List[dict], json.get('sites'))
    if not raw_sites:
      return {}
    for entity in raw_sites:
      sites[entity['id']] = Site(entity)
    return sites
