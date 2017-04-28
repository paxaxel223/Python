# -*- coding: utf-8 -*-
#!/usr/bin/env python
#
# Copyright 2012-2017 BigML
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import time
import json
import os
from datetime import datetime, timedelta
from world import world
from nose.tools import eq_, assert_less

from read_lda_steps import i_get_the_topic_model

from bigml.api import HTTP_CREATED
from bigml.api import HTTP_ACCEPTED
from bigml.api import FINISHED
from bigml.api import FAULTY
from bigml.api import get_status

#@step(r'I create a Topic Model')
def i_create_a_topic_model(step):
    dataset = world.dataset.get('resource')
    resource = world.api.create_topic_model(
        dataset, {'seed': 'BigML', 'topicmodel_seed': 'BigML'})
    world.status = resource['code']
    eq_(world.status, HTTP_CREATED)
    world.location = resource['location']
    world.topic_model = resource['object']
    world.topic_models.append(resource['resource'])

#@step(r'I create a topic model from a dataset list$')
def i_create_a_topic_model_from_dataset_list(step):
    resource = world.api.create_topic_model(world.dataset_ids)
    world.status = resource['code']
    eq_(world.status, HTTP_CREATED)
    world.location = resource['location']
    world.topic_model = resource['object']
    world.topic_models.append(resource['resource'])


#@step(r'I create a topic model with options "(.*)"$')
def i_create_a_topic_model_with_options(step, options):
    dataset = world.dataset.get('resource')
    options = json.loads(options)
    options.update({'seed': 'BigML',
                    'topicmodel_seed': 'BigML'})
    resource = world.api.create_topic_model(
        dataset, options)
    world.status = resource['code']
    eq_(world.status, HTTP_CREATED)
    world.location = resource['location']
    world.topic_model = resource['object']
    world.topic_models.append(resource['resource'])


#@step(r'I update the topic model name to "(.*)"$')
def i_update_topic_model_name(step, name):
    resource = world.api.update_topic_model(world.topic_model['resource'],
                                            {'name': name})
    world.status = resource['code']
    eq_(world.status, HTTP_ACCEPTED)
    world.location = resource['location']
    world.topic_model = resource['object']


#@step(r'I wait until the topic model status code is either (\d) or (-\d) less than (\d+)')
def wait_until_topic_model_status_code_is(step, code1, code2, secs):
    start = datetime.utcnow()
    i_get_the_topic_model(step, world.topic_model['resource'])
    status = get_status(world.topic_model)
    while (status['code'] != int(code1) and
           status['code'] != int(code2)):
           time.sleep(3)
           assert_less(datetime.utcnow() - start, timedelta(seconds=int(secs)))
           i_get_the_topic_model(step, world.topic_model['resource'])
           status = get_status(world.topic_model)
    eq_(status['code'], int(code1))

#@step(r'I wait until the topic model is ready less than (\d+)')
def the_topic_model_is_finished_in_less_than(step, secs):
    wait_until_topic_model_status_code_is(step, FINISHED, FAULTY, secs)

#@step(r'I make the topic model shared')
def make_the_topic_model_shared(step):
    resource = world.api.update_topic_model(world.topic_model['resource'],
                                            {'shared': True})
    world.status = resource['code']
    eq_(world.status, HTTP_ACCEPTED)
    world.location = resource['location']
    world.topic_model = resource['object']

#@step(r'I get the topic_model sharing info')
def get_sharing_info(step):
    world.shared_hash = world.topic_model['shared_hash']
    world.sharing_key = world.topic_model['sharing_key']

#@step(r'I check the topic model status using the topic model\'s shared url')
def topic_model_from_shared_url(step):
    world.topic_model = world.api.get_topic_model("shared/topicmodel/%s" %
                                          world.shared_hash)
    eq_(get_status(world.topic_model)['code'], FINISHED)

#@step(r'I check the topic model status using the topic model\'s shared key')
def topic_model_from_shared_key(step):

    username = os.environ.get("BIGML_USERNAME")
    world.topic_model = world.api.get_topic_model( \
        world.topic_model['resource'],
        shared_username=username, shared_api_key=world.sharing_key)
    eq_(get_status(world.topic_model)['code'], FINISHED)


#@step(r'the topic model name is "(.*)"')
def i_check_topic_model_name(step, name):
    topic_model_name = world.topic_model['name']
    eq_(name, topic_model_name)

def i_create_a_topic_distribution(step, data=None):
    if data is None:
        data = "{}"
    topic_model = world.topic_model['resource']
    data = json.loads(data)
    resource = world.api.create_topic_distribution(topic_model, data)
    world.status = resource['code']
    eq_(world.status, HTTP_CREATED)
    world.location = resource['location']
    world.topic_distribution = resource['object']
    world.topic_distributions.append(resource['resource'])

#@step(r'I create a local topic distribution')
def i_create_a_local_topic_distribution(step, data=None):
    world.local_topic_distribution = \
        world.local_topic_model.distribution(json.loads(data))
