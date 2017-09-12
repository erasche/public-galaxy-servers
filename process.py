#!/usr/bin/env python
import csv
import datetime
import simplejson
import json
import requests
import logging
logging.basicConfig(level=logging.DEBUG)


def munge(value):
    if value == 'yes':
        return True
    elif value == 'no':
        return False
    elif len(value.strip()) == 0:
        return None
    else:
        return value


data = []
with open('servers.csv', 'r') as csvfile:
    reader = csv.reader(csvfile)
    cols = next(reader)
    for row in reader:
        data.append({
            k: munge(v) for (k, v) in zip(cols, row)
        })


INTERESTING_FEATURES = (
    'allow_user_creation',
    'allow_user_dataset_purge',
    'brand',
    'enable_communication_server',
    'enable_openid',
    'enable_quotas',
    'enable_unique_workflow_defaults',
    'ftp_upload_site',
    'has_user_tool_filters',
    'message_box_visible',
    'message_box_content',
    'mailing_lists',
    'require_login',
    'server_startttime',
    'support_url',
    'terms_url',
    'wiki_url',
    'use_remote_user',
    'logo_src',
    'logo_url',
    'inactivity_box_content',
    'citation_url'
)


def assess_features(data):
    return {
        k: v for (k, v) in data.items()
        if k in INTERESTING_FEATURES
    }


def req_url_safe(url):
    try:
        r = requests.get(url, timeout=30)
    except requests.exceptions.ConnectTimeout:
        # If we cannot connect in time
        logging.debug("%s down, connect timeout", url)
        return None, 'connect'
    except requests.exceptions.SSLError as sle:
        # Or they have invalid SSL
        logging.debug("%s down, bad ssl", url)
        return None, 'ssl'
    except Exception as exc:
        # Or there is some OTHER exception
        logging.debug("%s down", url)
        return None, 'unk'
    # Ok, hopefully here means we've received a good response
    logging.debug("%s ok", url)
    return r, None


def req_json_safe(url):
    (r, error) = req_url_safe(url)
    if r is None:
        return r, error

    # Now we try decoding it as json.
    try:
        print(r)
        data = r.json()
    except simplejson.scanner.JSONDecodeError as jse:
        logging.debug("%s json_error: %s", url, jse)
        return None, 'json'

    return r, data


def no_api(url):
    # Ok, something went wrong, let's try the home page.
    (response, data) = req_url_safe(url)
    if data is None:
        # and something went wrong again, so we will call it down permanently.
        logging.info("%s down, bad ssl", response)
        return {
            'server': url,
            'responding': False,
            'galaxy': False,
        }

    if response.ok and 'window.Galaxy' in response.text:
        # If, however, window.Galaxy is in the text of the returned page...
        return {
            'server': url,
            'responding': True,
            'galaxy': True,
        }
    # Here we could not access the API and we also cannot access
    # the homepage.
    logging.info("%s inaccessible ok=%s galaxy in body=%s", url, response.ok, 'window.Galaxy' in response.text)
    return {
        'server': url,
        'responding': True,
        'galaxy': False,
    }


def process_url(url):
    (response, data) = req_json_safe(url + '/api/configuration')
    if data is None:
        return no_api(url)

    # then we have a good contact for /api/configuration
    if 'version_major' not in data:
        return no_api(url)

    version = data['version_major']
    features = assess_features(response.json())
    # Ok, api is responding, but main page must be as well.
    (response_index, data_index) = req_url_safe(url)

    if response_index.ok and 'window.Galaxy' in response_index.text:
        return {
            'server': url,
            'responding': True,
            'galaxy': True,

            'version': version,
            # how responsive is their server
            'response_time': response.elapsed.total_seconds(),
            # What interesting features does this galaxy have.
            'features': features,
        }
    return {
        'server': url,
        'responding': True,
        'galaxy': False,
        'version': version,
        'response_time': response_index.elapsed.total_seconds(),
        'code': response_index.status_code,
        'features': features,
    }


responses = []
for row in data:
    if 'url' not in row:
        logging.info("missing url for entry")
        continue
    url = row['url'].rstrip('/')
    responses.append(process_url(url))


today = datetime.datetime.now().strftime("%Y-%m-%d-%H")
with open(today + '.json', 'w') as handle:
    json.dump(responses, handle)
