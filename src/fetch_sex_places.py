import configparser
import csv
import datetime
import lzma
import math
import os
import re
from io import StringIO
from itertools import chain
from multiprocessing import Process, Queue
from shutil import copyfile
from urllib.parse import urlencode

import pandas as pd
import requests
from geopy.distance import vincenty

DATE = datetime.date.today().strftime('%Y-%m-%d')
OUTPUT = os.path.join('data', '{}-sex-place-distances.xz'.format(DATE))

settings = configparser.RawConfigParser()
settings.read('config.ini')


class SexPlacesSearch:

    BASE_URL = 'https://maps.googleapis.com/maps/api/place/'

    def __init__(self, key):
        self.GOOGLE_API_KEY = key

    def by_keyword(self, company, keywords):
        """
        :param company: (dict) with latitude and longitude keys (as floats)
        :param keyworks: (iterable) list of keywords
        """
        for keyword in keywords:
            msg = 'Looking for a {} nearby {} ({})…'
            print(msg.format(keyword, company['name'], company['cnpj']))

            # Create the request for the Nearby Search Api. The Parameter
            # rankby=distance will return a ordered list by distance
            lat, lng = company['latitude'], company['longitude']
            latlong = '{},{}'.format(lat, lng)
            nearby = requests.get(self.nearby_url(latlong, keyword)).json()

            if nearby['status'] != 'OK':
                if 'error_message' in nearby:
                    print('{}: {}'.format(nearby.get('status'),
                                          nearby.get('error_message')))
                elif nearby.get('status') != 'ZERO_RESULTS':
                    msg = 'Google Places API Status: {}'
                    print(msg.format(nearby.get('status')))

            # If have some result for this keywork, get first
            else:
                try:
                    place = nearby.get('results')[0]
                    location = deep_get(place, ['geometry', 'location'])
                    latitude = float(location.get('lat'))
                    longitude = float(location.get('lng'))
                    distance = vincenty((lat, lng), (latitude, longitude))
                    cnpj = ''.join(re.findall(r'[\d]', company['cnpj']))
                    yield {
                        'id': place.get('place_id'),
                        'keyword': keyword,
                        'latitude': latitude,
                        'longitude': longitude,
                        'distance': distance.meters,
                        'cnpj': cnpj
                    }
                except TypeError:
                    pass

    def with_details(self, place):
        """
        :param place: dictonary with id key.
        :return: dictionary updated with name, address and phone.
        """
        place_id = place.get('id')
        if not place_id:
            return place

        details = requests.get(self.details_url(place.get('id'))).json()
        if not details:
            return place

        name = deep_get(details, ['result', 'name'])
        address = deep_get(details, ['result', 'formatted_address'], '')
        phone = deep_get(details, ['result', 'formatted_phone_number'], '')

        place.update(dict(name=name, address=address, phone=phone))
        return place

    def near_to(self, company):
        """
        Return a dictonary containt information of the nearest sex place
        arround a given company. A sex place is some company that match a
        keyword (see `keywords` tuple) in a Google Places search.

        :param company: (dict) with latitude and longitude keys (as floats)
        :return: (dict) with
            * name : The name of nearest sex place
            * latitude : The latitude of nearest sex place
            * longitude : The longitude of nearest sex place
            * distance : Distance (in meters) between the company and the
              nearest sex place
            * address : The address of the nearest sex place
            * phone : The phone of the nearest sex place
            * id : The Google Place ID of the nearest sex place
            * keyword : term that matched the sex place in Google Place Search
        """
        keywords = ('Acompanhantes',
                    'Adult Entertainment Club',
                    'Adult Entertainment Store',
                    'Gay Sauna',
                    'Massagem',
                    'Modeling Agency',
                    'Motel',
                    'Night Club',
                    'Sex Club',
                    'Sex Shop',
                    'Strip Club',
                    'Swinger clubs')

        # for a case of nan in parameters
        lat, lng = float(company['latitude']), float(company['longitude'])
        if math.isnan(lat) or math.isnan(lng):
            return None

        # Get the closest place inside all the searched keywords
        sex_places = list(self.by_keyword(company, keywords))
        try:
            closest = min(sex_places, key=lambda x: x['distance'])
        except ValueError:
            return None  # i.e, not sex place found nearby

        # skip "hotel" when category is "motel"
        place = self.with_details(closest)
        name = place['name']
        if name:
            if 'hotel' in name.lower() and place['keyword'] == 'Motel':
                return None

        return place

    def details_url(self, place):
        """
        :param place: (int or str) ID of the place in Google Place
        :return: (str) URL to do a place details Google Places search
        """
        query = (('placeid', place),)
        return self.google_places_url('details', query)

    def nearby_url(self, location, keyword):
        """
        :param location: (str) latitude and longitude separeted by a comma
        :param keywork: (str) category to search places
        :return: (str) URL to do a nearby Google Places search
        """
        query = (
            ('location', location),
            ('keyword', keyword),
            ('rankby', 'distance'),
        )
        return self.google_places_url('nearbysearch', query)

    def google_places_url(self, endpoint, query=None, format='json'):
        """
        :param endpoint: (str) Google Places API endpoint name (e.g. details)
        :param query: (tuple) tuples with key/values pairs for the URL query
        :param format: (str) output format (default is `json`)
        :return: (str) URL to do an authenticated Google Places request
        """
        key = ('key', self.GOOGLE_API_KEY)
        query = tuple(chain(query, (key,))) if query else (key)
        parts = (
            self.BASE_URL,
            endpoint,
            '/{}?'.format(format),
            urlencode(query)
        )
        return ''.join(parts)


def sex_places_neraby(companies):
    """
    :param companies: pandas dataframe.
    """

    def make_queue(q, companies):
        for company in companies.itertuples(index=False):
            company = dict(company._asdict())  # _asdict() gives OrderedDict
            sex_place = sex_place_nearby(company)
            if sex_place:
                q.put(csv_line_as_string(sex_place))

    write_queue = Queue()
    place_search = Process(target=make_queue, args=(write_queue, companies))
    place_search.start()

    with lzma.open(OUTPUT, 'at') as output:
        while place_search.is_alive() or not write_queue.empty():
            try:
                contents = write_queue.get(timeout=1)
                if contents:
                    print(contents, file=output)
            except:
                pass

    place_search.join()


def sex_place_nearby(company):
    """
    :param company: (dict)
    :return: (dict) sex place
    """
    latitude, longitude = company.get('latitude'), company.get('longitude')
    if not latitude or not longitude:
        msg = 'No geolocation information for company: {} ({})'
        print(msg.format(company['name'], company['cnpj']))
        return None

    sex_place = SexPlacesSearch(settings.get('Google', 'APIKey'))
    return sex_place.near_to(company)


def csv_line_as_string(company=None, **kwargs):
    """
    Receives a given company (dict) and returns a string representnig this
    company data in a CSV format. CSV headers are defined in `fieldnames`.
    The named argument `headers` (bool) determines if the string includes the
    CSV header (if True) or not (if False, the default).
    """
    headers = kwargs.get('headers', False)
    if not company and not headers:
        return None

    csv_io = StringIO()
    fieldnames = ('id', 'keyword', 'latitude', 'longitude', 'distance', 'name',
                  'address', 'phone', 'cnpj')
    writer = csv.DictWriter(csv_io, fieldnames=fieldnames)

    if headers:
        writer.writeheader()

    if company:
        contents = {k: v for k, v in company.items() if k in fieldnames}
        writer.writerow(contents)

    contents = csv_io.getvalue()
    csv_io.close()
    return contents


def get_companies_dataset_path():
    return get_dataset_path(r'^[\d-]{11}companies.xz$')


def get_sex_places_dataset_path():
    return get_dataset_path(r'^[\d-]{11}sex-place-distances.xz$')


def get_dataset_path(regex):
    for file_name in os.listdir('data'):
        if re.compile(regex).match(file_name):
            return os.path.join('data', file_name)


def deep_get(dictionary, keys, default=None):
    """
    Returns values from nested dictionaries in a safe way (avoids KeyError).

    :param: (dict) usually a nested dict
    :param: (list) keys as strings
    :return: value or None

    Example:
    >>> d = {'ahoy': {'capn': 42}}
    >>> deep_get(['ahoy', 'capn'], d)
    42
    """
    if not keys:
        return None

    if len(keys) == 1:
        return dictionary.get(keys[0], default)

    return deep_get(dictionary.get(keys[0], {}), keys[1:])


if __name__ == '__main__':

    # get companies dataset
    companies_path = get_companies_dataset_path()
    companies = pd.read_csv(companies_path, low_memory=False)

    # check for existing sexp places dataset
    sex_places_path = get_sex_places_dataset_path()
    if sex_places_path:
        sex_places = pd.read_csv(sex_places_path, low_memory=False)
        if sex_places_path != OUTPUT:
            copyfile(sex_places_path, OUTPUT)
        try:
            remaining = companies[~companies.cnpj.isin(sex_places.cnpj)]
        except AttributeError:  # if file exists but is empty
            remaining = companies

    # start a sex places dataset if it doesn't exist
    else:
        with lzma.open(OUTPUT, 'at') as output:
            print(csv_line_as_string(headers=True), file=output)
        remaining = companies
        sex_places = pd.read_csv(get_sex_places_dataset_path())

    # run
    msg = """
    There are {} companies in {}.
    It looks like we already have the nearest sex location for {} of them.
    Yet {} company surroundings haven't been searched for sex places.

    Let's get started!
    """.format(
        len(companies),
        companies_path,
        len(sex_places),
        len(remaining)
    )
    print(msg)
    sex_places_neraby(remaining)
