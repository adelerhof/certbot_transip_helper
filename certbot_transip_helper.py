#!/usr/bin/env python3

import configparser
import dns.resolver  # pip3 install dnspython
import json
import os
import time
import transipApiV6

# Get environment variables that Certbot passes to us.
certbot_domain = os.getenv('CERTBOT_DOMAIN')
certbot_validation = os.getenv('CERTBOT_VALIDATION')
certbot_auth_output = os.getenv('CERTBOT_AUTH_OUTPUT')

# Entry that has to be in there for the validation
acme_entry = '_acme-challenge'

# Reading the ini file for configuation settings.
config_file = os.path.expanduser('~') + '/.certbot_transip_helper.ini'
config = configparser.ConfigParser()
if len(config.read(config_file)) != 1:
    print('Configfile "{}" not found'.format(config_file))
    exit(1)

if 'DEFAULT' not in config:
    print('No "DEFAULT" section in "{}"'.format(config_file))
    exit(1)

if 'login' not in config['DEFAULT']:
    print('No "login" in "DEFAULT" section in "{}"'.format(config_file))
    exit(1)

if 'keyfile' not in config['DEFAULT']:
    print('No "keyfile" in "DEFAULT" section in "{}"'.format(config_file))
    exit(1)

# Open and read key file.
key_file = open(config['DEFAULT']['keyfile'], "r")
key = key_file.read()
key_file.close()

# Get Header for authentication against transip api V6
headers = transipApiV6.Generic(config['DEFAULT']['login'], key).get_headers()

# Request domains managed by this account
domains=transipApiV6.Domains(headers)

# Request DNS entries for this domain
dns_entries = domains.list_dns_entries(certbot_domain)

# Check or there are "old" entries
found_dns_entries = []
for dns_entry in dns_entries['dnsEntries']:
  if dns_entry['name'] == acme_entry and dns_entry['type'] == 'TXT':
      found_dns_entries.append(dns_entry)

# Remove found "old" entries
print('{} entries found which have to be removed'.format(len(found_dns_entries)))
print('Removing: ',end='')
for dns_entry in found_dns_entries:
  domains.delete_dns_entry(certbot_domain,'{"dnsEntry": ' + json.dumps(dns_entry) + '}')
  print('.',end='')
print()

# Add entry new entry for validation only when needed, when certbot_auth_output is set nothing should be created so the script just cleans old entries
if certbot_auth_output is None:
  data = '''{
    "dnsEntry": {
      "name": "''' + acme_entry + '''",
      "expire": 60,
      "type": "TXT",
      "content": "''' + certbot_validation + '''"
    }
  }
  '''
  domains.add_dns_entry(certbot_domain, data)
  print('Entry for {}.{} created'.format(acme_entry,certbot_domain))

  # Wait and check until new entry can be resolved (could take a while), before continue
  sleep_interval = 10
  max_tries = 100
  failed = True
  print('Waiting for getting succesfull DNS result: ',end='')
  for x in range (max_tries):
      try:
          print('.',end='')
          time.sleep(sleep_interval)
          res = str(dns.resolver.query(acme_entry + '.' + certbot_domain, "TXT").response.answer[0][-1]).replace('"','')
          if certbot_validation == res:
              failed = False
              print()
              break
      except:
          pass

  # End of the retries so check or it has succeded.
  if failed:
      print()
      print('Checking for DNS change succesfull failed.')
      exit(1)
  print('Entry resolved succesfully')
